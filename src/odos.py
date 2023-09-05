import time
import json
import random
import requests
from web3 import Web3
from loguru import logger as logging

from src.account import Account
from src.utils import check_allowance, value_for_logs
from config import TOKENS, ODOS_ROUTER_ADDRESS, PROXY, GAS_THRESHOLD


class Odos:
    def __init__(self, account: Account, retries: int = 2):
        self.w3 = account.w3
        self.retries = retries
        self.account = account
        self.router_address = Web3.to_checksum_address(ODOS_ROUTER_ADDRESS)

    def swap(self, from_token: str, to_token: str, amount: int, retry: int = 0) -> bool:
        address = Web3.to_checksum_address(self.account.address)
        from_token_address = Web3.to_checksum_address(TOKENS[from_token] if from_token != 'eth' else TOKENS['zero_address'])
        to_token_address = Web3.to_checksum_address(TOKENS[to_token] if to_token != 'eth' else TOKENS['zero_address'])

        try:
            if from_token != 'eth':
                token = self.w3.eth.contract(address=from_token_address, abi=json.load(open('ABIs/erc20_abi.json')))
                check_allowance(self.w3, token, address, self.router_address, amount, self.account.key)

            quote = self.quote(address, from_token_address, to_token_address, amount)

            assemble_request_body = {
                "userAddr": address,
                "pathId": quote["pathId"]
            }

            swap_txn = self.get_api_call_data("https://api.odos.xyz/sor/assemble", assemble_request_body)
            amountOut = int(swap_txn['outputTokens'][0]['amount'])

            swap_txn = swap_txn['transaction']
            swap_txn['to'] = self.router_address
            swap_txn['chainId'] = self.w3.eth.chain_id
            swap_txn['value'] = int(swap_txn['value'])
            swap_txn['nonce'] = self.w3.eth.get_transaction_count(address)
            swap_txn['maxFeePerGas'] = self.w3.eth.gas_price
            swap_txn['maxPriorityFeePerGas'] = self.w3.eth.gas_price
            swap_txn['gas'] = random.randint(890000, 1000000) if GAS_THRESHOLD < 21 else self.w3.eth.estimate_gas(txn)
            del swap_txn['gasPrice']

            signed_swap_txn = self.w3.eth.account.sign_transaction(swap_txn, self.account.key)
            swap_txn_hash = self.w3.eth.send_raw_transaction(signed_swap_txn.rawTransaction)
            status = self.w3.eth.wait_for_transaction_receipt(swap_txn_hash, timeout=300).status

            if status == 1:
                trx = f'https://explorer.zksync.io/tx/{swap_txn_hash.hex()}'
                logging.success(f'{address} | Odos swap: {value_for_logs(from_token, amount)} -> '
                                f'{value_for_logs(to_token, amountOut)} | TRANSACTION: {trx}')
                return True
            else:
                logging.error(f'{address} | Odos swap {retry}/{self.retries} | {value_for_logs(from_token, amount)}'
                              f' -> {to_token}')
                if retry < self.retries:
                    time.sleep(random.randint(35, 60))
                    self.swap(from_token, to_token, amount, retry + 1)
                else:
                    return False

        except Exception as err:
            logging.error(f'{address} | Odos swap {retry}/{self.retries} | {value_for_logs(from_token, amount)}'
                          f' -> {to_token} | {err}')
            if retry < self.retries:
                time.sleep(random.randint(35, 60))
                self.swap(from_token, to_token, amount, retry + 1)
            else:
                return False

    def quote(self, address: str, from_token_address: str, to_token_address: str, amount: int):
        quote_url = 'https://api.odos.xyz/sor/quote/v2'

        quote_request_body = {
            "chainId": 324,
            "inputTokens": [
                {
                    "tokenAddress": from_token_address,
                    "amount": str(amount),
                }
            ],
            "outputTokens": [
                {
                    "tokenAddress": to_token_address,
                    "proportion": 1
                }
            ],
            "slippageLimitPercent": 0.3,  # slippage (1 = 1%)
            "userAddr": address,
            "referralCode": 0,
            "compact": True,
        }

        return self.get_api_call_data(quote_url, quote_request_body)

    @staticmethod
    def get_api_call_data(url, data=None):
        proxy = PROXY.split(':')
        headers = {"Content-Type": "application/json"}

        try:
            proxy = f'http://{proxy[2]}:{proxy[3]}@{proxy[0]}:{proxy[1]}'
            proxies = {
                'http': proxy,
                'https': proxy,
            }

            if data:
                response = requests.post(url=url, json=data, headers=headers, proxies=proxies)
            else:
                response = requests.get(url=url, proxies=proxies)
        except Exception:
            if data:
                response = requests.post(url=url, json=data, headers=headers)
            else:
                response = requests.get(url=url)
        if response.status_code == 200:
            api_data = response.json()
            return api_data
        else:
            return False

    def check_response(self):
        try:
            return self.get_api_call_data(f'https://api.odos.xyz/pricing/token/324/{TOKENS["usdc"]}?currencyId=ETH')
        except Exception as err:
            logging.error(f'Error: {err}')
            return False

    def get_amount_out(self, from_token: str, from_token_address: str, from_amount: float):
        currency_id = 'USD' if from_token == 'eth' else 'ETH'

        url = f'https://api.odos.xyz/pricing/token/324/{from_token_address}?currencyId={currency_id}'
        data = self.get_api_call_data(url)
        price = data['price']
        print(price)

        amount_out = from_amount * int(price)
        return int(amount_out * 10 ** 6) if from_token == 'eth' else int(Web3.to_wei(amount_out, 'ether'))
