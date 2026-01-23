#!/usr/bin/env python3
"""
Cloudflare Magic Transit Monitor
Monitora attacchi DDoS e gestisce automaticamente i prefissi BGP
"""

import requests
import json
import time
import logging
import sys
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import threading

# Configurazione
CONFIG_FILE = "/root/Cloudflare_MT_Integration/config/settings.json"
PREFIX_MAP_FILE = "/root/Cloudflare_MT_Integration/config/prefix_mapping.json"
LOG_DIR = "/root/Cloudflare_MT_Integration/logs"
LOG_FILE = f"{LOG_DIR}/monitor.log"

# Crea directory logs se non esiste
os.makedirs(LOG_DIR, exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class CloudflareMonitor:
    def __init__(self):
        """Inizializza il monitor"""
        self.load_config()
        self.load_prefix_mapping()
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        self.active_attacks = {}  # Track degli attacchi attivi
        self.prefix_timers = {}   # Timer per il ritiro dei prefissi
        self.advertised_prefixes = {}  # Track dei prefissi annunciati
        
    def load_config(self):
        """Carica la configurazione"""
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
            self.account_id = config['cloudflare']['account_id']
            self.api_token = config['cloudflare']['api_token']
            logger.info(f"Configurazione caricata per account: {self.account_id}")
        except Exception as e:
            logger.error(f"Errore nel caricamento configurazione: {e}")
            sys.exit(1)
    
    def load_prefix_mapping(self):
        """Carica la mappatura dei prefissi"""
        try:
            with open(PREFIX_MAP_FILE, 'r') as f:
                self.prefix_map = json.load(f)['prefixes']
            logger.info(f"Caricati {len(self.prefix_map)} prefissi")
        except Exception as e:
            logger.error(f"Errore nel caricamento prefix mapping: {e}")
            sys.exit(1)
    
    def send_telegram_notification(self, message: str):
        """Invia notifica Telegram"""
        telegram_token = "YOUR_TELEGRAM_BOT_TOKEN"
        chat_id = "YOUR_TELEGRAM_CHAT_ID"
        
        try:
            url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            response = requests.post(url, json=data, timeout=10)
            if response.status_code == 200:
                logger.info("Notifica Telegram inviata con successo")
            else:
                logger.warning(f"Errore invio Telegram: {response.status_code}")
        except Exception as e:
            logger.error(f"Errore invio notifica Telegram: {e}")
    
    def check_prefix_status(self, prefix: str) -> Tuple[bool, Optional[str]]:
        """Controlla se un prefisso è annunciato"""
        prefix_info = self.prefix_map.get(prefix)
        if not prefix_info:
            return False, None
        
        prefix_id = prefix_info['prefix_id']
        bgp_prefix_id = prefix_info.get('bgp_prefix_id')
        
        if not bgp_prefix_id:
            # Recupera BGP prefix ID
            url = f"{self.base_url}/accounts/{self.account_id}/addressing/prefixes/{prefix_id}/bgp/prefixes"
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('result'):
                    bgp_prefix_id = data['result'][0].get('id')
                    self.prefix_map[prefix]['bgp_prefix_id'] = bgp_prefix_id
        
        if not bgp_prefix_id:
            return False, None
        
        # Controlla stato
        url = f"{self.base_url}/accounts/{self.account_id}/addressing/prefixes/{prefix_id}/bgp/prefixes/{bgp_prefix_id}"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                result = data.get('result', {})
                advertised = result.get('on_demand', {}).get('advertised', False)
                advertised_at = result.get('on_demand', {}).get('advertised_modified_at')
                return advertised, advertised_at
        
        return False, None

    def check_advertise_constraint(self, modified_at: Optional[str]) -> Tuple[bool, float, Optional[str]]:
        """Check if the 15-minute constraint is satisfied for RE-ADVERTISE after withdrawal

        Returns:
            tuple: (can_advertise, remaining_seconds, advertise_time_str)
        """
        if not modified_at:
            return True, 0, None

        try:
            mod_time = datetime.fromisoformat(modified_at.replace('Z', '+00:00'))
            advertise_time = mod_time + timedelta(minutes=15)
            now = datetime.now(timezone.utc)

            if now >= advertise_time:
                return True, 0, None
            else:
                remaining = (advertise_time - now).total_seconds()
                # Format advertise time in local timezone (UTC+1 for Switzerland)
                advertise_time_local = advertise_time + timedelta(hours=1)
                advertise_time_str = advertise_time_local.strftime('%H:%M:%S')
                return False, remaining, advertise_time_str
        except:
            return True, 0, None

    def advertise_prefix(self, prefix: str) -> bool:
        """Annuncia un prefisso BGP"""
        prefix_info = self.prefix_map.get(prefix)
        if not prefix_info:
            logger.error(f"Prefisso {prefix} non trovato nella mappatura")
            return False

        prefix_id = prefix_info['prefix_id']
        bgp_prefix_id = prefix_info.get('bgp_prefix_id')

        if not bgp_prefix_id:
            logger.error(f"BGP prefix ID non trovato per {prefix}")
            return False

        # Check current status and 15-minute constraint
        advertised, advertised_at = self.check_prefix_status(prefix)
        if not advertised and advertised_at:
            can_advertise, remaining, advertise_time = self.check_advertise_constraint(advertised_at)
            if not can_advertise:
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                logger.warning(f"⏳ Cannot advertise {prefix} - 15-minute constraint not satisfied")
                logger.warning(f"   Advertise available at {advertise_time} (in {mins}m {secs}s)")
                return False

        url = f"{self.base_url}/accounts/{self.account_id}/addressing/prefixes/{prefix_id}/bgp/prefixes/{bgp_prefix_id}"
        data = {
            "on_demand": {
                "advertised": True
            }
        }

        response = requests.patch(url, headers=self.headers, json=data)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                logger.info(f"✅ Prefisso {prefix} annunciato con successo")
                self.advertised_prefixes[prefix] = datetime.now()
                
                # Notifica Telegram
                msg = f"""🛡️ *MAGIC TRANSIT ATTIVATO*

📡 *Prefisso Annunciato:* `{prefix}`
📝 *Descrizione:* {prefix_info.get('description', 'N/A')}
🌐 *ASN:* {prefix_info.get('asn', 'N/A')}
⏰ *Timestamp:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

_Attivazione automatica per mitigazione DDoS_"""
                self.send_telegram_notification(msg)
                return True
            else:
                logger.error(f"Errore annuncio {prefix}: {result.get('errors')}")
        else:
            logger.error(f"Errore HTTP {response.status_code} annunciando {prefix}")
        
        return False
    
    def withdraw_prefix(self, prefix: str) -> bool:
        """Ritira un prefisso BGP"""
        prefix_info = self.prefix_map.get(prefix)
        if not prefix_info:
            logger.error(f"Prefisso {prefix} non trovato nella mappatura")
            return False
        
        prefix_id = prefix_info['prefix_id']
        bgp_prefix_id = prefix_info.get('bgp_prefix_id')
        
        if not bgp_prefix_id:
            logger.error(f"BGP prefix ID non trovato per {prefix}")
            return False
        
        url = f"{self.base_url}/accounts/{self.account_id}/addressing/prefixes/{prefix_id}/bgp/prefixes/{bgp_prefix_id}"
        data = {
            "on_demand": {
                "advertised": False
            }
        }
        
        response = requests.patch(url, headers=self.headers, json=data)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                logger.info(f"✅ Prefisso {prefix} ritirato con successo")
                
                # Calcola durata annuncio
                duration = "N/A"
                if prefix in self.advertised_prefixes:
                    start_time = self.advertised_prefixes[prefix]
                    elapsed = datetime.now() - start_time
                    duration = str(elapsed).split('.')[0]
                    del self.advertised_prefixes[prefix]
                
                # Notifica Telegram
                msg = f"""🔚 *MAGIC TRANSIT DISATTIVATO*

📡 *Prefisso Ritirato:* `{prefix}`
📝 *Descrizione:* {prefix_info.get('description', 'N/A')}
⏱️ *Durata Annuncio:* {duration}
⏰ *Timestamp:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

_Ritiro automatico dopo fine attacco DDoS_"""
                self.send_telegram_notification(msg)
                return True
            else:
                logger.error(f"Errore ritiro {prefix}: {result.get('errors')}")
        else:
            logger.error(f"Errore HTTP {response.status_code} ritirando {prefix}")
        
        return False
    
    def schedule_prefix_withdrawal(self, prefix: str, delay_seconds: int = 900):
        """Schedula il ritiro di un prefisso dopo un delay"""
        if prefix in self.prefix_timers:
            # Cancella timer esistente
            self.prefix_timers[prefix].cancel()
        
        logger.info(f"⏰ Schedulato ritiro di {prefix} tra {delay_seconds} secondi")
        
        timer = threading.Timer(delay_seconds, self.withdraw_prefix, args=[prefix])
        timer.start()
        self.prefix_timers[prefix] = timer
    
    def check_ddos_attacks(self) -> List[Dict]:
        """Controlla attacchi DDoS recenti via GraphQL"""
        url = f"{self.base_url}/graphql"
        
        # Query per attacchi negli ultimi 5 minuti
        five_minutes_ago = (datetime.utcnow() - timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        query = """
        query GetRecentAttacks($accountTag: string!, $datetimeStart: Time!) {
            viewer {
                accounts(filter: { accountTag: $accountTag }) {
                    dosdNetworkAnalytics(
                        filter: {
                            datetime_geq: $datetimeStart
                            outcome: "drop"
                        }
                        orderBy: [datetime_DESC]
                        limit: 1000
                    ) {
                        dimensions {
                            datetime
                            attackId
                            destinationIP
                            destinationPort
                            ipProtocol
                            mitigationReason
                            outcome
                        }
                        sum {
                            packets
                            bits
                        }
                    }
                }
            }
        }
        """
        
        variables = {
            "accountTag": self.account_id,
            "datetimeStart": five_minutes_ago
        }
        
        try:
            response = requests.post(url, headers=self.headers, json={
                "query": query,
                "variables": variables
            }, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if not data.get('errors'):
                    accounts = data.get('data', {}).get('viewer', {}).get('accounts', [])
                    if accounts:
                        analytics = accounts[0].get('dosdNetworkAnalytics', [])
                        return analytics
            else:
                logger.error(f"Errore GraphQL: HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"Errore nel check attacchi: {e}")
        
        return []
    
    def process_attacks(self, attack_data: List[Dict]):
        """Processa i dati degli attacchi"""
        current_attacks = {}
        affected_prefixes = set()
        
        for event in attack_data:
            dimensions = event.get('dimensions', {})
            metrics = event.get('sum', {})
            
            dest_ip = dimensions.get('destinationIP')
            attack_id = dimensions.get('attackId')
            packets = metrics.get('packets', 0)
            
            if not dest_ip:
                continue
            
            # Trova il prefisso corrispondente
            for prefix in self.prefix_map.keys():
                if self.is_ip_in_prefix(dest_ip, prefix):
                    affected_prefixes.add(prefix)
                    
                    if attack_id:
                        if attack_id not in current_attacks:
                            current_attacks[attack_id] = {
                                'prefixes': set(),
                                'total_packets': 0,
                                'start_time': dimensions.get('datetime'),
                                'dest_ips': set()
                            }
                        current_attacks[attack_id]['prefixes'].add(prefix)
                        current_attacks[attack_id]['total_packets'] += packets
                        current_attacks[attack_id]['dest_ips'].add(dest_ip)
        
        # Confronta con attacchi precedenti
        new_attacks = set(current_attacks.keys()) - set(self.active_attacks.keys())
        ended_attacks = set(self.active_attacks.keys()) - set(current_attacks.keys())
        
        # Gestisci nuovi attacchi
        for attack_id in new_attacks:
            attack_info = current_attacks[attack_id]
            logger.warning(f"🚨 NUOVO ATTACCO RILEVATO: {attack_id}")
            logger.info(f"   Prefissi coinvolti: {attack_info['prefixes']}")
            logger.info(f"   Pacchetti totali: {attack_info['total_packets']:,}")
            
            # Annuncia prefissi coinvolti
            for prefix in attack_info['prefixes']:
                advertised, _ = self.check_prefix_status(prefix)
                if not advertised:
                    logger.info(f"📡 Annuncio prefisso {prefix} per mitigazione")
                    self.advertise_prefix(prefix)
                    
                    # Cancella eventuali timer di ritiro in corso
                    if prefix in self.prefix_timers:
                        self.prefix_timers[prefix].cancel()
                        del self.prefix_timers[prefix]
            
            # Notifica Telegram per nuovo attacco
            msg = f"""🚨 *ATTACCO DDoS RILEVATO*

🆔 *Attack ID:* `{attack_id}`
📡 *Prefissi Coinvolti:* {', '.join(f'`{p}`' for p in attack_info['prefixes'])}
📊 *Pacchetti:* {attack_info['total_packets']:,}
🎯 *IP Target:* {', '.join(list(attack_info['dest_ips'])[:3])}
⏰ *Rilevato:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

_Magic Transit attivato automaticamente_"""
            self.send_telegram_notification(msg)
        
        # Gestisci attacchi terminati
        for attack_id in ended_attacks:
            attack_info = self.active_attacks[attack_id]
            logger.info(f"✅ ATTACCO TERMINATO: {attack_id}")
            
            # Schedula ritiro prefissi dopo 15 minuti
            for prefix in attack_info['prefixes']:
                if prefix not in affected_prefixes:  # Non sotto attacco attuale
                    self.schedule_prefix_withdrawal(prefix, delay_seconds=900)
            
            # Notifica Telegram per fine attacco
            msg = f"""✅ *ATTACCO DDoS TERMINATO*

🆔 *Attack ID:* `{attack_id}`
📡 *Prefissi:* {', '.join(f'`{p}`' for p in attack_info['prefixes'])}
⏱️ *Durata:* {self.calculate_duration(attack_info.get('start_time'))}
📅 *Ritiro prefissi:* tra 15 minuti
⏰ *Terminato:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
            self.send_telegram_notification(msg)
        
        # Aggiorna stato attacchi attivi
        self.active_attacks = current_attacks
    
    def is_ip_in_prefix(self, ip: str, prefix: str) -> bool:
        """Controlla se un IP appartiene a un prefisso"""
        try:
            import ipaddress
            ip_obj = ipaddress.ip_address(ip)
            network_obj = ipaddress.ip_network(prefix)
            return ip_obj in network_obj
        except:
            return False
    
    def calculate_duration(self, start_time: str) -> str:
        """Calcola la durata da un timestamp"""
        try:
            if start_time:
                start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                duration = datetime.now(start.tzinfo) - start
                return str(duration).split('.')[0]
        except:
            pass
        return "N/A"
    
    def monitor_loop(self):
        """Loop principale di monitoraggio"""
        logger.info("=" * 60)
        logger.info("AVVIO CLOUDFLARE MAGIC TRANSIT MONITOR")
        logger.info("=" * 60)
        logger.info(f"Account: {self.account_id}")
        logger.info(f"Intervallo polling: 180 secondi")
        logger.info(f"Ritiro prefissi: 15 minuti dopo fine attacco")
        logger.info("=" * 60)
        
        # Notifica avvio
        self.send_telegram_notification(
            "🚀 *Magic Transit Monitor AVVIATO*\n\n"
            f"📊 Prefissi monitorati: {len(self.prefix_map)}\n"
            f"⏰ Polling: ogni 3 minuti\n"
            f"🔄 Ritiro automatico: 15 min dopo fine attacco"
        )
        
        while True:
            try:
                logger.debug("Controllo attacchi DDoS...")
                
                # Controlla attacchi
                attack_data = self.check_ddos_attacks()
                
                if attack_data:
                    logger.info(f"Trovati {len(attack_data)} eventi di mitigazione")
                    self.process_attacks(attack_data)
                else:
                    logger.debug("Nessun attacco rilevato")
                
                # Log stato prefissi annunciati
                if self.advertised_prefixes:
                    logger.info(f"Prefissi attualmente annunciati: {list(self.advertised_prefixes.keys())}")
                
                # Attendi prossimo ciclo
                time.sleep(180)  # 3 minuti
                
            except KeyboardInterrupt:
                logger.info("\n⏹️  Arresto monitor richiesto")
                
                # Cancella tutti i timer
                for timer in self.prefix_timers.values():
                    timer.cancel()
                
                # Notifica arresto
                self.send_telegram_notification(
                    "⏹️ *Magic Transit Monitor ARRESTATO*\n\n"
                    f"Prefissi ancora annunciati: {len(self.advertised_prefixes)}"
                )
                break
                
            except Exception as e:
                logger.error(f"Errore nel loop di monitoraggio: {e}")
                time.sleep(60)  # Attendi 1 minuto in caso di errore

def main():
    monitor = CloudflareMonitor()
    monitor.monitor_loop()

if __name__ == "__main__":
    main()