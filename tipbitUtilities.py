import requests
import json
import os
import msvcrt
from decimal import Decimal
import hashlib, binascii

from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
from http.client import CannotSendRequest

import botSpecificData

rpc_connection = None

MAX_CONSOLE_MESSAGE_STACK = 10

lastConsoleMessage = ''
lastConsoleMessageCount = 0

CurrentUSDPrice = 9999999.0

def ConnectViaRPC():
	global rpc_connection
	rpc_connection = AuthServiceProxy('http://{}:{}@127.0.0.1:{}'.format(botSpecificData.rpc_user, botSpecificData.rpc_password, botSpecificData.port))

#  Prints to the console, but saves off multiple prints to batch them into one of max size (MAX_CONSOLE_MESSAGE_STACK) if they are repetitive
def ConsolePrint(string):
	global lastConsoleMessage
	global lastConsoleMessageCount

	if (lastConsoleMessage == string):
		lastConsoleMessageCount += 1
		if (lastConsoleMessageCount >= MAX_CONSOLE_MESSAGE_STACK):
			print('{} (x {})'.format(string, lastConsoleMessageCount))
			lastConsoleMessageCount = 0
	else:
		if (lastConsoleMessageCount > 0):
			print('{} (x {})'.format(lastConsoleMessage, lastConsoleMessageCount))
		lastConsoleMessageCount = 0
		lastConsoleMessage = string
		print(string)
		
def isRedditorValid(redditor):
	try:
		redditor.id
		return True
	except:
		return False
			
def isStringFloat(amountString):
	try:
		return (amountString.replace('.','',1).isdigit() is True)
	except ValueError:
		return False
		
def GetBitcoinValue(printValue, tipBalance):
	global CurrentUSDPrice
	CurrentUSDPrice = Decimal(requests.get('https://bitpay.com/api/rates/usd').json()['rate'])
	if printValue: ConsolePrint('Bitcoin value: ${} (Total Tip Balance is worth ${}'.format("%.2f" % CurrentUSDPrice, "%.2f" % (CurrentUSDPrice * SatoshisToBTC(tipBalance))))
		
def SatoshisToBTC(satoshis):
	return Decimal(satoshis) / Decimal(100000000.0)
		
def SatoshisToMBTC(satoshis):
	return Decimal(satoshis) / Decimal(100000.0)
	
def SatoshisToUSD(satoshis):
	return Decimal(satoshis) * Decimal(CurrentUSDPrice) / Decimal(100000000.0)
	
def BTCToSatoshis(btc):
	return int(Decimal(btc) * Decimal(100000000.0))
	
def BTCToMBTC(btc):
	return Decimal(btc) * Decimal(1000.0)
	
def MBTCToSatoshis(btc):
	return int(Decimal(btc) * Decimal(100000.0))
	
def MBTCToBTC(btc):
	return Decimal(btc) / Decimal(1000.0)
	
def USDToSatoshis(usd, printOutput=False):
	satoshis = Decimal(usd) / Decimal(CurrentUSDPrice) * Decimal(100000000.0)
	if printOutput: print('USDToSatoshis({}) = {} [Current USD Price: {}]'.format(usd, int(satoshis), "%.2f" % CurrentUSDPrice))
	return satoshis

#  If the ESCAPE key is detected, exit the program cleanly
def checkForInput(userBalances):
	if not msvcrt.kbhit(): return
	key = ord(msvcrt.getch())

	if (key is 27): # ESCAPE
		ConsolePrint("Detected ESCAPE key press. Closing down the bot...")
		exit()
	elif (key is 98): # b
		PrintAccountBalancesList()
		ConsolePrint("============================================================")
		print(userBalances)
		ConsolePrint("")
	elif (key is 32): # SPACEBAR
		ConsolePrint("============================================================")
		ConsolePrint("")
		
##### RPC UTILITIES - UNUSED

def GetReceivedByAddressList():
	print('UNUSED UTILITY FUNCTION: GetReceivedByAddressList')
	receivedByAddresses = rpc_connection.listreceivedbyaddress(0)
	return receivedByAddresses
	
def GetBlockchainInfo():
	print('UNUSED UTILITY FUNCTION: GetBlockchainInfo')
	blockchainInfo = rpc_connection.getblockchaininfo()
	return blockchainInfo

def PrintReceivedByAddresses():
	print('UNUSED UTILITY FUNCTION: PrintReceivedByAddresses')
	receivedByAddresses = GetReceivedByAddressList()
	print('Received by: {}\n'.format(receivedByAddresses))

def PrintBlockchainInfo():
	print('UNUSED UTILITY FUNCTION: PrintBlockchainInfo')
	blockchainInfo = GetBlockchainInfo()
	print('Blockchain Info:\n{}\n'.format(blockchainInfo))
	
##### RPC UTILITIES - LEVEL 1 (all used RPC calls in here)

def GetAccountsList():
	accountsList = []
	try:
		accountsList = rpc_connection.listaccounts(3, True)
	except ConnectionAbortedError:
		print('ConnectionAbortedError Exception in GetAccountsList(). Returning blank list.')
	except CannotSendRequest:
		print('CannotSendRequest Exception in GetAccountsList(). Returning blank list.')
	return accountsList
	
def GetAddressListForAccount(account):
	addressList = rpc_connection.getaddressesbyaccount(account)
	return addressList
	
def SetAddressToAccount(address, account):
	rpc_connection.setaccount(address, account)
	
def GetPrivateKeyFromAddress(address):
	try:
		privateKey = rpc_connection.dumpprivkey(address)
		return privateKey
	except JSONRPCException:
		print('JSONRPCException in GetPrivateKeyFromAddress on address {}'.format(address))
		return ''
		
def GetAccountBalance(account):
	print('DEPRECATED: YOU SHOULD NOT USE ACCOUNTS (GetAccountBalance)')
	return rpc_connection.getbalance(account, 3)
		
def ImportPrivateKey(privateKey, account = '', rescan = True):
	try:
		rpc_connection.importprivkey(privateKey, account, rescan)
		return True
	except JSONRPCException:
		print('JSONRPCException in ImportPrivateKey on key {}'.format(privateKey))
		return False
	except ValueError:
		print('ValueError in ImportPrivateKey on key {}'.format(privateKey))
		return False
	
def GetNewLegacyAddress(account):
	address = rpc_connection.getnewaddress(account)
	return address
	
def GetNewSegwitAddress(account, addressLegacy, printLegacy=False):
	if printLegacy: print('GetNewSegwitAddress({}, {})'.format(account, addressLegacy))
	address = rpc_connection.addwitnessaddress(addressLegacy)
	SetAddressToAccount(address, account)
	return address
	
def GetUnspentsList():
	unspentList = []
	try:
		unspentList = rpc_connection.listunspent(1)
	except ConnectionAbortedError:
		ConsolePrint('ConnectionAbortedError Exception in GetUnspentsList(). Returning blank list.')
	except CannotSendRequest:
		ConsolePrint('CannotSendRequest Exception in GetUnspentsList(). Returning blank list.')
	except socket.Timeouterror:
		ConsolePrint('Socket Timeout Error in GetUnspentsFromAddress...')
	return unspentList
	
def PrintUnspentsList():
	unspentsList = GetUnspentsList()
	print('PrintUnspentsList():')
	for unspent in unspentsList: print(' - {}'.format(unspent))

def CreateRawTransaction(inputs, inputsTotal, address, amount, changeAddress, fee = Decimal(0.0000)):
	feeBTC = SatoshisToBTC(fee)
	
	print('Creating raw transaction: [{} : {}]'.format(amount, inputsTotal))
	
	amount = min(amount, inputsTotal - feeBTC)
	outputs = {}
	outputs[address] = amount
	outputs[changeAddress] = inputsTotal - Decimal(amount) - feeBTC
	
	tx = rpc_connection.createrawtransaction(inputs, outputs)
	return tx
	
def SignRawTransaction(rawTX):
	signedTX = rpc_connection.signrawtransaction(rawTX)
	print('Signed raw transaction')
	return signedTX
	
def SendRawTransaction(rawTX, printTX=False):
	sentTX = rpc_connection.sendrawtransaction(rawTX)
	if printTX: print('Sent raw transaction: {}'.format(sentTX))
	return sentTX
	
def SendFromAccountToAddress(account, address, amount):
	print('DEPRECATED: YOU SHOULD NOT USE ACCOUNTS (SendFromAccountToAddress)')
	print('Sending {} to {} from account {}'.format(amount, address, account))
	rpc_connection.sendfrom(account, address, amount)
	
#  Sends amount minus fee to the given address, returning the value of the fee amount in Satoshis
def SendFromAddressToAddress(addressFrom, addressTo, amount, feePerByte, falseSend=False):
	unspentsFromAddress = GetUnspentsFromAddress(addressFrom)
	unspentsTotal = GetUnspentsTotal(unspentsFromAddress)
	print('SendFromAddressToAddress [{} : {}]'.format(amount, feePerByte))
	rawTX = CreateRawTransaction(unspentsFromAddress, unspentsTotal, addressTo, amount, addressFrom)
	txLength = len(rawTX)
	fee = feePerByte * txLength
	if falseSend: return fee, rawTX
	rawTX = CreateRawTransaction(unspentsFromAddress, unspentsTotal, addressTo, amount, addressFrom, fee)
	signedTX = SignRawTransaction(rawTX)
	sentTX = SendRawTransaction(signedTX['hex'])
	return fee, sentTX
	
def MoveCoinsAccountToAccount(accountFrom, accountTo, amount):
	rpc_connection.move(accountFrom, accountTo, amount)
	
##### RPC UTILITIES - LEVEL 2 (functions that utilize basic RPC calls through level 1)
	
#  Returns a dictionary of wallets and their balances if they have any unspents
def GetWalletBalancesList():
	walletBalances = {}
	unspentsList = GetUnspentsList()
	for unspent in unspentsList:
		if (unspent['amount'] == Decimal(0)): continue
		if (unspent['address'] in walletBalances): walletBalances[unspent['address']] += unspent['amount']
		else: walletBalances[unspent['address']] = unspent['amount']

	return walletBalances
	
def PrintWalletBalancesList():
	walletBalances = GetWalletBalancesList()
	print('PrintWalletBalancesList():')
	for wallet in walletBalances: print('{}: {}'.format(wallet, BTCToSatoshis(walletBalances[wallet])))
	
#  Returns a dictionary of addresses to accounts
def GetAddressToAccountList():
	accountsList = GetAccountsList()
	addressToAccounts = {}
	for account in accountsList:
		addressList = GetAddressListForAccount(account)
		for address in addressList:	addressToAccounts[address] = account
	
	return addressToAccounts
	
#  Returns a list of all accounts (if they have a balance) and their balance
def GetAccountBalancesList():
	addressToAccounts = GetAddressToAccountList()
	walletBalances = GetWalletBalancesList()
	
	accountBalancesList = {}
	for wallet in walletBalances:
		if wallet not in addressToAccounts: continue
		if addressToAccounts[wallet] in accountBalancesList: accountBalancesList[addressToAccounts[wallet]] += walletBalances[wallet]
		else: accountBalancesList[addressToAccounts[wallet]] = walletBalances[wallet]
		
	return accountBalancesList
	
def PrintAccountBalancesList():
	accountBalancesList = GetAccountBalancesList()
	print('PrintAccountBalancesList():')
	for account in accountBalancesList: print('{}: {}'.format(account, BTCToSatoshis(accountBalancesList[account])))
	
def PrintAccountsList(onlyShowNonZero = False):
	print('DEPRECATED: YOU SHOULD NOT USE ACCOUNTS (PrintAccountsList)')
	accountsList = GetAccountsList()
	print('Accounts List:')
	for account in accountsList:
		if ((onlyShowNonZero is True) and (accountsList[account] == 0)): continue
		print(' - {} [{} BTC]'.format(account, accountsList[account]))
		
def PrintAddressesOnAccount(account):
	print('Addresses belonging to \"{}\":'.format(account))
	addressList = GetAddressListForAccount(account)
	for address in addressList:
		print(' - {}'.format(address))
	
def PrintPrivateKey(address):
	privateKey = GetPrivateKeyFromAddress(address)
	print('Address {} private key: \n - {}'.format(address, privateKey))
	
def GetUnspentsFromAddress(address, printUnspents=False):
	unspentList = GetUnspentsList()

	unspentFromAddress = []
	for unspent in unspentList[:-1]:
		if (unspent['address'] == address):
			entry = {}
			entry['txid'] = unspent['txid']
			entry['vout'] = unspent['vout']
			entry['amount'] = unspent['amount']
			unspentFromAddress.append(entry)
	if unspentList[-1]['address'] == address:
			entry = {}
			entry['txid'] = unspentList[-1]['txid']
			entry['vout'] = unspentList[-1]['vout']
			entry['amount'] = unspentList[-1]['amount']
			unspentFromAddress.append(entry)
	if printUnspents: print(unspentFromAddress)
	return unspentFromAddress
	
def GetUnspentsTotal(unspentFromAddress, printTotal=False):
	total = 0
	for unspent in unspentFromAddress:
		total += unspent['amount']
	if printTotal: print('Total: {}'.format(total))
	return total
	
##### UTILITIES - ADDRESSES AND ACCOUNTS
	
def ClaimExistingUserAddresses(userPrivateKeys, userDepositAddressesLegacy, userDepositAddressesSegwit, printSegwit=False):
	print('- Claiming Existing User Addresses...')
	for username in userPrivateKeys:
		ImportPrivateKey(userPrivateKeys[username], username, False)
	for username in userDepositAddressesLegacy:
		userDepositAddressesSegwit[username] = GetUnusedAddressSegwit(username + ' Segwit', userDepositAddressesLegacy[username])
		if printSegwit: print('Segwit Address ({}) = {}'.format(username, userDepositAddressesSegwit[username]))
	
def SaveOffUnusedAddresses(UnusedAddressesLegacy, UnusedAddressesSegwit):
	print('- Saving Off Unused Addresses...')
	segwitDeliminator = '2' if botSpecificData.testnet else '3'
	UnusedAddressesLegacy = []
	UnusedAddressesSegwit = []
	addressList = GetAddressListForAccount('')
	for address in addressList:
		if address[0] == segwitDeliminator:		UnusedAddressesSegwit.append(address)
		else:									UnusedAddressesLegacy.append(address)
	
def SaveOffUsedAddresses(UsedAddressesLegacy, UsedAddressesSegwit):
	print('- Saving Off Used Addresses...')
	segwitDeliminator = '2' if botSpecificData.testnet else '3'
	UsedAddressesLegacy = {}
	UsedAddressesSegwit = {}
	accountList = GetAccountsList()
	for account in accountList:
		if account == '': continue
		addressList = GetAddressListForAccount(account)
		for address in addressList:
			if address[0] == segwitDeliminator:		UsedAddressesSegwit[account] = address
			else:									UsedAddressesLegacy[account] = address
			
def GetUnusedAddressLegacy(unusedAddressesLegacy, account):
	if account in unusedAddressesLegacy:
		return unusedAddressesLegacy[account]
	
	if len(unusedAddressesLegacy) > 0:
		returnVal = unusedAddressesLegacy[0]
		SetAddressToAccount(returnVal, account)
		unusedAddressesLegacy.remove(returnVal)
		return returnVal
	else:
		returnVal = GetNewLegacyAddress(account)
		return returnVal
		
def GetUnusedAddressSegwit(account, addressLegacy):
	returnVal = GetNewSegwitAddress(account, addressLegacy)
	return returnVal
	
##### UTILITIES - DATA SAVE AND LOAD
	
def ExportUserBalancesJson(userBalances):
	filepath = "TNUserBalances.json" if botSpecificData.testnet else "UserBalances.json"
	with open(filepath, 'w') as f:
		json.dump(userBalances, f)

def ImportUserBalancesJson(userBalances, printBalances):
	filepath = "TNUserBalances.json" if botSpecificData.testnet else "UserBalances.json"
	if os.path.isfile(filepath):
		with open(filepath, "rb") as f:
			balances = json.load(f)
			for balance in balances:
				userBalances[balance] = balances[balance]
	
	if printBalances: print(userBalances)
				
def ExportUserDepositAddressesLegacyJson(userDepositAddressesLegacy):
	filepath = "TNUserDepositAddressesLegacy.json" if botSpecificData.testnet else "UserDepositAddressesLegacy.json"
	with open(filepath, 'w') as f:
		json.dump(userDepositAddressesLegacy, f)
				
def ImportUserDepositAddressesLegacyJson(userDepositAddressesLegacy):
	filepath = "TNUserDepositAddressesLegacy.json" if botSpecificData.testnet else "UserDepositAddressesLegacy.json"
	if os.path.isfile(filepath):
		with open(filepath, "rb") as f:
			addresses = json.load(f)
			for username in addresses:
				userDepositAddressesLegacy[username] = addresses[username]	
				
def ExportUserDepositAddressesSegwitJson(userDepositAddressesSegwit):
	filepath = "TNUserDepositAddressesSegwit.json" if botSpecificData.testnet else "UserDepositAddressesSegwit.json"
	with open(filepath, 'w') as f:
		json.dump(userDepositAddressesSegwit, f)
				
def ImportUserDepositAddressesSegwitJson(userDepositAddressesSegwit):
	filepath = "TNUserDepositAddressesSegwit.json" if botSpecificData.testnet else "UserDepositAddressesSegwit.json"
	if os.path.isfile(filepath):
		with open(filepath, "rb") as f:
			addresses = json.load(f)
			for username in addresses:
				userDepositAddressesSegwit[username] = addresses[username]	
				
def ExportUserPrivateKeysJson(userPrivateKeys):
	filepath = "TNUserPrivateKeys.json" if botSpecificData.testnet else "UserPrivateKeys.json"
	with open(filepath, 'w') as f:
		json.dump(userPrivateKeys, f)

def ImportUserPrivateKeysJson(userPrivateKeys):
	filepath = "TNUserPrivateKeys.json" if botSpecificData.testnet else "UserPrivateKeys.json"
	if os.path.isfile(filepath):
		with open(filepath, "rb") as f:
			usersToKeys = json.load(f)
			for username in usersToKeys:
				userPrivateKeys[username] = usersToKeys[username]