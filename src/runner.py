import time
import random
from web3 import Web3
from loguru import logger as logging

from src.inch import Inch
from src.odos import Odos
from src.woofi import WooFi
from src.account import Account
from src.spacefi import SpaceFi
from src.syncswap import SyncSwap
from src.main_bridge import MainBridge
from config import TOKENS, SLEEP_TRANSACTIONS, MIN_BALANCE_FOR_GAS, BALANCE_PERCENTAGE, BRIDGE, GAS_THRESHOLD


class Runner:
    def __init__(self, account: Account):
        self.account = account
        self.w3_eth = Web3(Web3.HTTPProvider("https://eth.llamarpc.com"))
        self.tokens = {'eth': 0.35, 'usdc': 0.25, 'usdt': 0.2, 'busd': 0.2}  # token: proba
        self.dapps = {
            'odos': Odos(self.account),
            'inch': Inch(self.account),
            'woofi': WooFi(self.account),
            'spacefi': SpaceFi(self.account),
            'syncswap': SyncSwap(self.account)
        }

    def start(self):
        address = self.account.address
        transactions = self.account.db[address]["transactions"]
        
        response_status = self.dapps['odos'].check_response()
        if not response_status and self.account.progress['volumes']:
            logging.warning(f'{address} | Не удалось установить соединение с Odos, добавьте прокси в config.py')
            return
        elif not response_status:
            del self.dapps['odos']

        if self.account.progress['volumes']:
            self.volumes_runner()
        else:
            self.base_runner()
        
        completed_trx = transactions - self.account.progress["transactions"]
        if completed_trx == 0:
            return
        elif self.account.progress["transactions"] == 0:
            logging.info(f'{address} | Прогон завершен')
        else:
            logging.info(f'{address} | Выполнено {completed_trx} транзакций')

    def base_runner(self):
        try:
            from_token = self.account.get_max_balance_token()
        except Exception as err:
            logging.error(f'Проблемы с rpc: {err}')
            return

        if not BRIDGE and self.account.get_native_balance() > 0:
            self.account.progress['bridge'] = False

        if self.account.progress['bridge']:
            status = MainBridge(self.account).deposit()
            self.account.progress['bridge'] = False
            time.sleep(random.randint(60, 120))
            while self.account.get_native_balance() == 0 and status:
                time.sleep(random.randint(60, 120))

        iters_per_dapps = self.account.init_iters_per_dapps()
        for iters in iters_per_dapps:
            self.gas_tracker()
            dapp_name = random.choice(list(self.dapps.keys()))
            dapp = self.dapps[dapp_name]
            from_token, to_token = self.choice_token_pair(dapp_name, self.tokens, from_token)

            for _ in range(iters):
                amount = self.get_amount(from_token)
                if amount < 0 or from_token == to_token:
                    logging.error(f'{self.account.address} | Недостаточно ETH для оплаты газа')
                    return

                if not dapp.swap(from_token, to_token, amount):
                    break

                self.stake_runner(dapp, dapp_name, to_token)

                self.account.progress['transactions'] -= 1
                self.account.save_db()
                from_token, to_token = self.choice_token_pair(dapp_name, self.tokens, to_token)
                time.sleep(random.randint(*SLEEP_TRANSACTIONS))

    def volumes_runner(self):
        transactions_threshold = random.randint(10, 13)
        transactions = self.account.progress['transactions']
        transactions = transactions_threshold if transactions > transactions_threshold else transactions

        dapp = self.dapps['odos']

        try:
            from_token = self.account.get_max_balance_token()
        except Exception as err:
            logging.error(f'Проблемы с rpc: {err}')
            return

        if from_token == 'usdt':
            amount = self.get_amount(from_token, True)
            if amount < 0:
                logging.error(f'{self.account.address} | Недостаточно ETH для оплаты газа')
                return
            dapp.swap(from_token, 'eth', amount)
            from_token = 'eth'
            time.sleep(random.randint(*SLEEP_TRANSACTIONS))

        odos_tokens = self.tokens
        del odos_tokens['usdt']

        from_token, to_token = self.choice_token_pair('odos', odos_tokens, from_token)

        for _ in range(transactions):
            self.gas_tracker()

            amount = self.get_amount(from_token, True)
            if amount < 0 or from_token == to_token:
                logging.error(f'{self.account.address} | Недостаточно ETH для оплаты газа')
                return
            elif not dapp.swap(from_token, to_token, amount):
                break

            self.account.progress['transactions'] -= 1
            self.account.save_db()
            from_token, to_token = self.choice_token_pair('odos', odos_tokens, to_token)
            time.sleep(random.randint(*SLEEP_TRANSACTIONS))

    def stake_runner(self, dapp, dapp_name, to_token):
        time.sleep(random.randint(*SLEEP_TRANSACTIONS))

        if dapp_name == 'spacefi' and self.account.check_enough_fee() and self.account.progress['spacefi_deposit'] > 0:
            if dapp.add_liquidity(to_token):
                self.account.progress['spacefi_deposit'] -= 1
                self.account.save_db()
        elif dapp_name == 'syncswap' and self.account.check_enough_fee() and self.account.progress['syncswap_deposit'] > 0:
            if dapp.add_liquidity():
                self.account.progress['syncswap_deposit'] -= 1
                self.account.save_db()

    def choice_token_pair(self, dapp_name: str, tokens: dict, to_token: str) -> tuple:
        from_token = to_token
        random_dex = random.choice(['syncswap', 'spacefi'])

        if not self.account.check_enough_fee():
            return 'eth', 'eth'
        elif from_token != 'eth' and self.account.get_native_balance() < 0.000635 * 10 ** 18:
            if dapp_name == 'woofi':
                self.dapps[random_dex].swap(from_token, 'eth', self.get_amount(from_token))
                time.sleep(random.randint(*SLEEP_TRANSACTIONS))
                from_token = 'eth'

            return from_token, 'eth'

        if dapp_name == 'woofi':
            to_token = 'usdc' if from_token == 'eth' else 'eth'
            if from_token not in ['eth', 'usdc']:
                self.dapps[random_dex].swap(from_token, to_token, self.get_amount(from_token))
                time.sleep(random.randint(*SLEEP_TRANSACTIONS))
                from_token, to_token = self.choice_token_pair(dapp_name, tokens, to_token)

            return from_token, to_token

        tokens_temp = {token: p for token, p in tokens.items() if token != from_token}
        proba = [p / sum(list(tokens_temp.values())) for p in list(tokens_temp.values())]
        to_token = random.choices(list(tokens_temp.keys()), proba)[0]
        return from_token, to_token

    def get_amount(self, from_token: str, volumes: bool = False) -> int:
        if from_token == 'eth' and volumes:
            amount = self.account.get_native_balance() - int(random.uniform(*MIN_BALANCE_FOR_GAS) * 10 ** 18)
        elif from_token == 'eth':
            amount = (self.account.get_native_balance() - 0.00027 * 10 ** 18) * random.uniform(*BALANCE_PERCENTAGE)
        else:
            amount = self.account.get_token_data(TOKENS[from_token])['balance_wei']

        return int(amount)

    def gas_tracker(self):
        gas_price = Web3.from_wei(self.w3_eth.eth.gas_price, 'gwei')
        while gas_price > GAS_THRESHOLD:
            print(f'Gas price: {round(gas_price, 1)}')
            time.sleep(30)
            gas_price = Web3.from_wei(self.w3_eth.eth.gas_price, 'gwei')
