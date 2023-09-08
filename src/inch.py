import time
import json
import random
import requests
from web3 import Web3
from loguru import logger as logging

from src.account import Account
from src.utils import check_allowance, value_for_logs
from config import TOKENS, INCH_ROUTER_ADDRESS, GAS_THRESHOLD


class Inch:
    def __init__(self, account: Account, retries: int = 1):
        self.w3 = account.w3
        self.account = account
        self.retries = retries
        self.router_address = Web3.to_checksum_address(INCH_ROUTER_ADDRESS)

    def swap(self, from_token: str, to_token: str, amount: int, retry: int = 0) -> bool:
        eth = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
        address = Web3.to_checksum_address(self.account.address)

        try:
            from_token_address = Web3.to_checksum_address(TOKENS[from_token] if from_token != 'eth' else eth)
            to_token_address = Web3.to_checksum_address(TOKENS[to_token] if to_token != 'eth' else eth)

            if from_token != 'eth':
                token = self.w3.eth.contract(address=from_token_address, abi=json.load(open('ABIs/erc20_abi.json')))
                check_allowance(self.w3, token, address, self.router_address, amount, self.account.key)

            swap_quote = f'https://api-defillama.1inch.io/v5.0/{self.w3.eth.chain_id}/swap?fromTokenAddress={from_token_address}&toTokenAddress={to_token_address}&amount={amount}&fromAddress={address}&slippage=5'
            # swap_quote = f'https://api.1inch.io/v5.0/{self.w3.eth.chain_id}/swap?fromTokenAddress={from_token_address}&toTokenAddress={to_token_address}&amount={amount}&fromAddress={address}&slippage={5}'

            tx = self.get_api_call_data(swap_quote)

            tx = tx['tx']
            tx['nonce'] = self.w3.eth.get_transaction_count(address)
            tx['to'] = self.router_address
            tx['value'] = int(tx['value'])
            tx['maxFeePerGas'] = self.w3.eth.gas_price
            tx['maxPriorityFeePerGas'] = self.w3.eth.gas_price
            tx['chainId'] = self.w3.eth.chain_id
            tx['gas'] = random.randint(900000, 950000) if GAS_THRESHOLD < 21 else self.w3.eth.estimate_gas(tx)
            del tx['gasPrice']

            swap_txn_hash = self.sign_trans(tx, self.account.key)
            status = self.w3.eth.wait_for_transaction_receipt(swap_txn_hash, timeout=300).status

            if status == 1:
                trx = f'https://explorer.zksync.io/tx/{swap_txn_hash.hex()}'
                logging.success(f'{address} | 1inch swap: {from_token} -> {to_token}: '
                                f'{value_for_logs(from_token, amount)} | TRANSACTION: {trx}')
                return True
            else:
                logging.error(f'{address} | 1inch swap {retry}/{self.retries} | {value_for_logs(from_token, amount)}'
                              f' -> {to_token}')
                if retry < self.retries:
                    time.sleep(random.randint(35, 60))
                    self.swap(from_token, to_token, amount, retry + 1)
                else:
                    return False

        except Exception as err:
            logging.error(f'{address} | 1inch swap {retry}/{self.retries} | {value_for_logs(from_token, amount)}'
                          f' -> {to_token} | {err}')
            if retry < self.retries:
                time.sleep(random.randint(35, 60))
                self.swap(from_token, to_token, amount, retry + 1)
            else:
                return False

    def sign_trans(self, swap_txn, key):
        signed_swap_txn = self.w3.eth.account.sign_transaction(swap_txn, key)
        swap_txn_hash = self.w3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
        return swap_txn_hash

    @staticmethod
    def get_api_call_data(url):
        try:
            response = requests.get(url)
        except Exception:
            response = requests.get(url)
        if response.status_code == 200:
            api_data = response.json()
            return api_data
        else:
            return False
