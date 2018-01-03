import requests
import json

DEFAULT_TIMEOUT = 10

lastConsoleMessage = ''
lastConsoleMessageCount = 0

#  Prints to the console, but saves off multiple prints to batch them into one of max size (10) if they are repetitive
def ConsolePrint(string):
	global lastConsoleMessage

	if (lastConsoleMessage == string):
		lastConsoleMessageCount += 1
		if (lastConsoleMessageCount >= 10):
			print('{} (x {})'.format(string, lastConsoleMessageCount))
			lastConsoleMessageCount = 0
	else:
		if (lastConsoleMessageCount > 0):
			print('{} (x {})'.format(string, lastConsoleMessageCount))
		lastConsoleMessageCount = 0
		lastConsoleMessage = string
		print(string)

#  Returns the unconfirmed transaction balance delta of the given address
def get_unconfirmed_delta(address):
	IGNORED_ERRORS = (ConnectionError, requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.ReadTimeout, json.decoder.JSONDecodeError)
	endpoint = 'https://blockchain.info/address/{}?format=json'

	unconfirmed_delta = 0
	try:
		transactions = []
		offset = 0
		payload = {'offset': str(offset)}
		txs_per_page = 50

		response = requests.get(endpoint.format(address), timeout=DEFAULT_TIMEOUT).json()
		total_txs = response['n_tx']

		while total_txs > 0:
			for item in response['txs']:
				if 'block_height' not in item.keys():
					for out in item['out']:
						if out['addr'] == address:
							unconfirmed_delta += out['value']

			total_txs -= txs_per_page
			offset += txs_per_page
			payload['offset'] = str(offset)
			response = requests.get(endpoint.format(address),
									params=payload,
									timeout=DEFAULT_TIMEOUT).json()
	except IGNORED_ERRORS:
		return 0

	return unconfirmed_delta
				
#  Used for get_balance below
def get_balance_BitpayAPI(address):
	r = requests.get('https://insight.bitpay.com/api/addr/{}/balance'.format(address), timeout=DEFAULT_TIMEOUT)
	if r.status_code != 200:  # pragma: no cover
		raise ConnectionError
	return r.json()
			
#  Used for get_balance below
def get_balance_SmartbitAPI(address):
	r = requests.get('https://api.smartbit.com.au/v1/blockchain/address/' + address + '?limit=1', timeout=DEFAULT_TIMEOUT)
	if r.status_code != 200:  # pragma: no cover
		raise ConnectionError
	return r.json()['address']['confirmed']['balance_int']
	
#  Use this instead of NetworkAPI.get_balance since that uses SmartbitAPI incorrectly, and BlockchainAPI which returns the wrong value (includes unconfirmed)
def get_balance(address):
	IGNORED_ERRORS = (ConnectionError, requests.exceptions.ConnectionError, requests.exceptions.Timeout, requests.exceptions.ReadTimeout)
	GET_BALANCE_MAIN = [get_balance_BitpayAPI, get_balance_SmartbitAPI]

	for api_call in GET_BALANCE_MAIN:
		try:
			return api_call(address)
		except IGNORED_ERRORS:
			pass

	ConsolePrint("ConnectionError: All APIs are unreachable.")