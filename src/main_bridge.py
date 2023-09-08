import json
import random
from web3 import Web3
from loguru import logger as logging

from src.account import Account
from config import OFFICIAL_BRIDGE, BRIDGE_AMOUNT, ETHEREUM_RPC


class MainBridge:
    def __init__(self, account: Account):
        self.w3 = Web3(Web3.HTTPProvider(ETHEREUM_RPC))
        self.account = account
        self.router_address = Web3.to_checksum_address(OFFICIAL_BRIDGE)
        self.router = self.w3.eth.contract(address=self.router_address, abi=json.load(open('ABIs/main_bridge.json')))

    def deposit(self):
        gas_limit = random.randint(700000, 850000)

        native_balance = self.w3.eth.get_balance(self.account.address)
        amount_for_fee = Web3.to_wei(0.003, 'ether')
        amount = int(random.uniform(*BRIDGE_AMOUNT) * 10 ** 18)

        if native_balance - amount_for_fee < amount:
            logging.warning(f'{self.account.address} | Main Bridge | Недостаточно баланса')

        try:
            base_cost = self.router.functions.l2TransactionBaseCost(self.w3.eth.gas_price, gas_limit, 800).call()

            txn = self.router.functions.requestL2Transaction(
                self.account.address,
                amount,
                "0x",
                gas_limit,
                800,
                [],
                self.account.address
            ).build_transaction({
                'from': self.account.address,
                'value': amount + base_cost,
                'gas': 0,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.account.address)
            })

            txn['gas'] = self.w3.eth.estimate_gas(txn)
            signed_txn = self.w3.eth.account.sign_transaction(txn, self.account.key)
            txn_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            status = self.w3.eth.wait_for_transaction_receipt(signed_txn, timeout=300).status

            if status == 1:
                trx = f'https://etherscan.io/tx/{txn_hash.hex()}'
                logging.success(f'{self.account.address} | Main Bridge | Ethereum -> ZkSync Era | TRANSACTION: {trx}')
                return True
            else:
                logging.error(f'{self.account.address} Error Main Bridge')
                return False

        except Exception as err:
            logging.error(f'{self.account.address} Error Main Bridge: {err}')
            return False
