# BIT IMPORTS
from bit import Key
from bit import wif_to_key
from bit.network.rates import currency_to_satoshi_cached
from bit.exceptions import InsufficientFunds
from bit.network import get_fee, get_fee_cached
from bit.network import satoshi_to_currency
from bit.network import NetworkAPI

# BASE IMPORTS
import pdb
import re
import os
import time
import pickle
import json
import msvcrt
import urllib3
import ssl
import threading
from tkinter import *

# PRAW IMPORTS
import praw
from praw.models import Message
from praw.models import Comment
from prawcore.exceptions import RequestException

#  SEPARATED CODE IMPORTS
import messageTemplates
import botSpecificData

reddit = praw.Reddit(botSpecificData.BOT_USERNAME)
BOT_MENTION = '/u/{}'.format(botSpecificData.BOT_USERNAME)
storageKey = Key(botSpecificData.STORAGE_PRIVATE_KEY)
STORAGE_ADDRESS = storageKey.address
	
#  Initialize the empty user balances dictionary
userBalances = {
	# 'exampleUserName' : 100000000,
	}
userBalancesCopy = {} # Used for the solvency check thread to avoid race conditions

#  Initialize the empty user deposit addresses dictionary
userDepositAddresses = {
	# 'exampleUserName' : 'EXAMPLE_ADDRESS'
	}
userDepositAddressesCopy = {} # Used for the deposit check thread to avoid race conditions

userDepositTransactions = {
	# 'exampleTX' : "username"
	}

#  Initialize the Key() array and the empty private key data dictionary
userKeyStructs = {}
userPrivateKeys = {
	# 'exampleUserName' : 'EXAMPLE_PRIVATE_KEY'
	}
	
unreadMessages = []
unreadMessageCount = 0
unreadMentions = []
unreadMentionCount = 0
allUnread = []
markedRead = []
unsentTipFailures = []
unsentTipSuccesses = []
unsentCommentCount = 0

allTipBalanceTotal = 0
storageBalance = 0
solvencyDiff = 0
lastSolvencyDiff = 0

#  Tkinter window data
window = Tk()
window.geometry('800x600')
window.resizable(width=False, height=False)
window.iconbitmap('TipBitIcon.ico')
window.title("TipBit - The Reddit Bitcoin Tip Bot")
canvas = Canvas(window, width=800, height=600)
canvas.pack()

#   GUI Editable Objects
tipBalanceStringVar = StringVar()
storageBalanceStringVar = StringVar()
tipStorageDiffStringVar = StringVar()
tipBalanceStringVar.set("tip_balance")
storageBalanceStringVar.set("storage_balance")
tipStorageDiffStringVar.set("tip_storage_difference")
eventListbox = Listbox(window, width=800, height=560)
eventListbox.place(x=0, y=40, anchor='nw')


def main():
	AddEventString('Bot ID: {}'.format(reddit.user.me()), False)

	#  Set up the GUI
	SetupGUI()
	
	#  Import all user data
	ImportAllUserData()
	
	#  Initiate the main loop function
	AddEventString("Initiating main loop", False)
	mainLoop()
	
def SetupGUI():
	Label(window, text='TIP BALANCE', anchor='center', justify=CENTER, font='Arial 9 bold').place(x=133, y=10, anchor='center')
	Label(window, textvariable=tipBalanceStringVar, anchor='center', justify=CENTER).place(x=133, y=28, anchor='center')
	Label(window, text='STORAGE BALANCE', anchor='center', justify=CENTER, font='Arial 9 bold').place(x=400, y=10, anchor='center')
	Label(window, textvariable=storageBalanceStringVar, anchor='center', justify=CENTER).place(x=400, y=28, anchor='center')
	Label(window, text='DIFFERENCE', anchor='center', justify=CENTER, font='Arial 9 bold').place(x=666, y=10, anchor='center')
	Label(window, textvariable=tipStorageDiffStringVar, anchor='center', justify=CENTER).place(x=666, y=28, anchor='center')
	canvas.create_line(0, 40, 800, 40)
	canvas.create_line(266, 0, 266, 40)
	canvas.create_line(533, 0, 533, 40)
	
def UpdateGUI():
	tipBalanceStringVar.set(allTipBalanceTotal)
	storageBalanceStringVar.set(storageBalance)
	tipStorageDiffStringVar.set(solvencyDiff)
	
def AddEventString(eventString, showInConsole=True):
	if showInConsole:
		global eventListbox
		eventListbox.insert(END, eventString)
	print(eventString)
	
def ImportAllUserData():
	#  Import the list of all user balances
	AddEventString("Importing user balances...", False)
	ImportUserBalancesJson()
	
	#  Import the list of all user deposit addresses
	AddEventString("Importing user deposit addresses...", False)
	ImportUserDepositAddressesJson()
	
	#  Import the list of all user private keys
	AddEventString("Importing user private keys...", False)
	ImportUserPrivateKeysJson()
	
	#  Import the list of all user deposit transactions
	AddEventString("Importing user deposit transactions...", False)
	ImportUserDepositTransactionsJson()
		
def mainLoop():
	lastMainLoopTime = time.time()
	lastUnsentCheckTime = time.time()
	lastSolvencyCheckTime = time.time()
	lastDepositCheckTime = time.time()
	
	global userBalancesCopy
	global userDepositAddressesCopy
	solvencyThread = 0
	depositsThread = 0

	while (True):
		try:
			#  Update the window handler and check for the ESCAPE key
			window.update_idletasks()
			window.update()
			checkForEscape()
			
			#  Run the main loop every 3.0 seconds
			if (time.time() < lastMainLoopTime): continue
			lastMainLoopTime = time.time() + 3.0
				
			#  Collect all unread mentions and messages
			gatherUnreads()
			
			#  Display any change in the current unread or unsent count
			displayUnreadUnsentCount()
			
			#  Attempt to re-post comments that failed to post if at least 10 seconds has gone by
			if (time.time() > lastUnsentCheckTime):
				processUnsent()
				lastUnsentCheckTime = time.time() + 10.0
			
			#  Check the next 5 messages
			processMessages()
			
			#  Check the next 5 comments
			processComments()
			
			#  Check for solvency if at least 240 seconds has gone by
			if ((solvencyThread == 0) or (not solvencyThread.isAlive())):
				UpdateGUI()
				if (time.time() > lastSolvencyCheckTime):
					userBalancesCopy = userBalances.copy()
					solvencyThread = threading.Thread(target=checkSolvency)
					solvencyThread.daemon = True
					solvencyThread.start()
					lastSolvencyCheckTime = time.time() + 240.0
				
			#  Check for any balance deposits if at least 120 seconds has gone by
			if (time.time() > lastDepositCheckTime):
				if ((depositsThread == 0) or (not depositsThread.isAlive())):
					userDepositAddressesCopy = userDepositAddresses.copy()
					depositsThread = threading.Thread(target=processDeposits)
					depositsThread.daemon = True
					depositsThread.start()
				lastDepositCheckTime = time.time() + 120.0
				
		except ConnectionError:
			AddEventString("ConnectionError occurred during processing...", False)
		except RequestException:
			AddEventString('RequestException on processing of unreads (likely a timeout / connection error)', False)
			
def gatherUnreads():
	#  Process all unread messages and comments, checking for exceptions along the way (particularly the ones common when using PRAW)
	global allUnread
	global markedRead
	allUnread = reddit.inbox.unread(limit=1)
	try:
		for item in allUnread:
			if (item in markedRead):
				AddEventString("reddit.inbox.unread is returning items after they're marked read... something is wrong")
				continue
			try:
				if isinstance(item, Message):
					unreadMessages.append(item)
				elif isinstance(item, Comment):
					unreadMentions.append(item)
			except urllib3.exceptions.ReadTimeoutError:
				AddEventString('ReadTimeoutError on processing of unread messages and comments...')
			except ssl.SSLError:
				AddEventString('SSL error on processing of unread messages and comments...')
			except Exception as e:
				print(e)
				AddEventString('Unknown exception on processing of unread messages and comments...')
	except RequestException:
		AddEventString('RequestException on processing of unreads (likely a timeout / connection error)', False)
	
	for item in unreadMessages: markedRead.append(item)
	for item in unreadMentions: markedRead.append(item)
	reddit.inbox.mark_read(unreadMessages)
	reddit.inbox.mark_read(unreadMentions)
		
def displayUnreadUnsentCount():
	#  If the unread mention count has changed, print a message
	global unreadMentionCount
	global unreadMessageCount
	global unsentCommentCount
	if ((len(unreadMentions) is not unreadMentionCount) or (len(unreadMessages) is not unreadMessageCount) or ((len(unsentTipFailures) + len(unsentTipSuccesses)) is not unsentCommentCount)):
		print("Comments / Messages / Unsent: [{}, {}, {}]".format(len(unreadMentions), len(unreadMessages), (len(unsentTipFailures) + len(unsentTipSuccesses))))
	unreadMentionCount = len(unreadMentions)
	unreadMessageCount = len(unreadMessages)
	unsentCommentCount = len(unsentTipFailures) + len(unsentTipSuccesses)

def checkForEscape():
	#  If the ESCAPE key is detected within the 3 seconds the bot sleeps per loop, the program exits cleanly
	if msvcrt.kbhit() and ord(msvcrt.getch()) is 27:
		AddEventString("Detected ESCAPE key press. Closing down the bot...")
		exit()

def processMessages():
	#  Hunt through the different subject lines we respond to. If it is anything else, toss it and mention it in console
	for message in unreadMessages:
		messageSubject = message.subject.upper()
		messageAuthor = message.author.name.lower()
		if (messageSubject == "REGISTER"):
			RegisterUser(messageAuthor, True)
		elif (messageSubject == "SWEEP DEPOSIT"):
			ProcessSweepDeposit(message)
		elif (messageSubject == "WITHDRAW"):
			ProcessWithdraw(message, True)
		elif (messageSubject == "WITHDRAW TEST"):
			ProcessWithdraw(message, False)
		elif (messageSubject == "BALANCE"):
			ProcessBalance(messageAuthor)
		else:
			AddEventString("Removing unknown message: {}".format(message))
		unreadMessages.remove(message)

def processComments():
	#  Recheck the comment for the bot name to ensure it still exists (could be a comment reply)
	for comment in unreadMentions:
		#  Ensure the comment mention was in the allowed subs. Can't have this thing leaking...
		subName = comment.subreddit.display_name.lower()
		if (subName in botSpecificData.BOT_TEST_SUBS):
			#  Process the comment if the bot is mentioned
			if (((botSpecificData.BOT_USERNAME + ' ') in comment.body.lower())):
				processSingleComment(comment, comment.body.lower())
		else:
			AddEventString('We received a comment in another subreddit: {}'.format(subName))
		unreadMentions.remove(comment)

def processSingleComment(comment, commentBody):
	#  Note: This function allows you to pass in an altered comment body, which will then get processed. The comment reference is only used to reply onto
	
	#  Grab the author's name to use for tipping and registration purposes
	senderName = comment.author.name.lower()
	
	if (senderName not in userBalances):
		CommentReply_TipFailure(comment, messageTemplates.TIP_FAILURE_UNREGISTERED_USER, '')
		AddEventString('User {} failed to tip (sender not registered)'.format(senderName))
		return False
	
	#  Ensure that either the bot username is the beginning of the comment, or there is a space before it
	separate_around_bot = commentBody.partition(botSpecificData.BOT_USERNAME + ' ')
	while (separate_around_bot[1] != ""):
		if ((separate_around_bot[1] == (botSpecificData.BOT_USERNAME + ' '))):
			#  Check if the next word is a username and if that user exists. If not, comment back as such
			separate_around_target = separate_around_bot[2].partition(" ")
			separate_around_bot = separate_around_target[2].partition(botSpecificData.BOT_USERNAME + ' ')
			
			targetName = separate_around_target[0].lower()
			if ('/u/' in targetName):
				targetName = targetName.partition('/u/')[2]
			redditor = reddit.redditor(targetName)
			if isRedditorValid(redditor) is False:
				#  TIP FAILURE: Reddit account could not be found through username specified in comment
				CommentReply_TipFailure(comment, messageTemplates.USERNAME_IS_REMOVED_OR_BANNED_TEXT, targetName)
				AddEventString('Failed to tip {} (non-existent account)'.format(targetName))
				continue
			else: #  Redditor is valid
				#  Ensure that the next string value is a number
				separate_around_amount = separate_around_target[2].partition(' ')
				if ('\n' in separate_around_amount[0]):
					separate_around_amount = separate_around_amount[0].partition('\n')
					
				amountString = separate_around_amount[0]
				amountSatoshi = getSatoshiFromAmountString(amountString)
				if amountSatoshi == -1:
					#  FAILED TIP: Amount not specified correctly in comment
					CommentReply_TipFailure(comment, messageTemplates.AMOUNT_NOT_SPECIFIED_TEXT, targetName)
					AddEventString('Failed to tip {} (unspecified amount: {})'.format(targetName, amountString))
					continue
				else:
					RegisterUser(senderName, False)
					if (not isBalanceSufficient(senderName, amountSatoshi)):
						#  FAILED TIP: Amount not available in user balance
						CommentReply_TipFailure(comment, messageTemplates.AMOUNT_NOT_AVAILABLE_TEXT, targetName)
						AddEventString('Failed to tip {} (insufficient balance)'.format(targetName))
						continue
					else:
						#  SUCCESSFUL TIP
						if (senderName is not targetName): processSingleTip(senderName, targetName, amountSatoshi)
						AddEventString('Successful tip: {} -> {} ({})'.format(senderName, targetName, amountSatoshi))
						CommentReply_TipSuccess(comment, senderName, targetName, amountSatoshi, satoshi_to_currency(amountSatoshi, 'usd'), botSpecificData.BOT_INTRO_LINK)
						continue
		else:
			AddEventString("Caught a comment reply with no mention. We should discourage these...")
			break

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
		
def getSatoshiFromAmountString(amountString):
	if (isStringFloat(amountString)):
		return int(currency_to_satoshi_cached(amountString, 'mbtc'))
	if (amountString in botSpecificData.AMOUNT_DICTIONARY):
		return getSatoshiFromAmountString(botSpecificData.AMOUNT_DICTIONARY[amountString])
	if (amountString[0] == '$'):
		amountString = amountString[1:]
		if (isStringFloat(amountString)):
			return int(currency_to_satoshi_cached(amountString, 'usd'))
		
	return -1
		

#  Attempt to comment about the tip failure, and save off the comment if we fail to post it
def CommentReply_TipFailure(comment, commentTemplate, targetUsername, firstTry=True):
	try:
		comment.reply(commentTemplate.format(targetUsername))
		return True
	except praw.exceptions.APIException as ex:
		if (firstTry is True): 
			print('Saving off tip failure comment due to exception: {}'.format(ex.error_type))
			failureComment = (comment, commentTemplate, targetUsername)
			unsentTipFailures.append(failureComment)
		return False
	except:
		AddEventString('Unknown error occurred while commenting on a successful tip...')
		return False
	
#  Attempt to comment about the tip success, and save off the comment if we fail to post it
def CommentReply_TipSuccess(comment, senderUsername, targetUsername, amountSatoshis, amountUSD, botInfoLink, firstTry=True):
	amountMBTC = satoshi_to_currency(amountSatoshis, 'mbtc')
	try:
		comment.reply(messageTemplates.SUCCESSFUL_TIP_TEXT.format(senderUsername, targetUsername, amountMBTC, amountUSD, botInfoLink))
		return True
	except praw.exceptions.APIException as ex:
		if (firstTry is True): 
			print('Saving off tip success comment due to exception: {}'.format(ex.error_type))
			successComment = (comment, senderUsername, targetUsername, amountSatoshis, amountUSD, botInfoLink)
			unsentTipSuccesses.append(successComment)
		return False
	except:
		AddEventString('Unknown error occurred while commenting on a successful tip...')
		return False

#  Attempt to post any comments that failed to post the first time (generally due to reddit API restricting posting too many comments too quickly)
def processUnsent():
	while (len(unsentTipFailures) > 0):
		failure = unsentTipFailures[0]
		if (CommentReply_TipFailure(failure[0], failure[1], failure[2], False) is False):
			break
		AddEventString('Successfully sent a previously blocked comment')
		unsentTipFailures.remove(failure)
		
	while len(unsentTipSuccesses) > 0:
		success = unsentTipSuccesses[0]
		if (CommentReply_TipSuccess(success[0], success[1], success[2], success[3], success[4], success[5], False) is False):
			break
		AddEventString('Successfully sent a previously blocked comment')
		unsentTipSuccesses.remove(success)

#  Process a sweep deposit, pushing money from a wallet with the given private key to our storage (to avoid the double transaction fee you get when using the normal deposit method)
def ProcessSweepDeposit(message):
	username = message.author.name.lower()
	userAccount = reddit.redditor(username)
	RegisterUser(username, False)
	
	AddEventString('Attempting Sweep Deposit: {}'.format(message.body))
	sweepKey = Key(message.body)
	sweepBalance = int(sweepKey.get_balance())
	if (sweepBalance < botSpecificData.MINIMUM_WITHDRAWAL):
		MINIMUM_DEPOSIT_MBTC = satoshi_to_currency(botSpecificData.MINIMUM_DEPOSIT, 'mbtc')
		AddEventString('Failed to perform sweep deposit for user [{}] (balance under minimum deposit)'.format(username))
		userAccount.message('Sweep Deposit failed!', messageTemplates.USER_FAILED_SWEEP_DEPOSIT_UNDER_MINIMUM_MESSAGE_TEXT.format(MINIMUM_DEPOSIT_MBTC))
		return False

	#  Attempt to prepare a transaction so we can determine the fee to take out so the user eats the cost
	depositBalance = sweepBalance
	storageTX = []
	estimatedFee = DetermineFee(sweepKey, STORAGE_ADDRESS, depositBalance, botSpecificData.STORAGE_TRANSFER_FEE_PER_BYTE)
	newDepositDelta = depositBalance - estimatedFee
	
	depositBalanceMBTC = satoshi_to_currency(depositBalance, 'mbtc')
	estimatedFeeMBTC = satoshi_to_currency(estimatedFee, 'mbtc')
	newDepositDeltaMBTC = satoshi_to_currency(newDepositDelta, 'mbtc')
	
	#  Now we should have an estimated fee, so we can subtract that from the amount we're sending, and transfer it
	storageTX = SendBitcoin(sweepKey, STORAGE_ADDRESS, depositBalance, estimatedFee, botSpecificData.STORAGE_TRANSFER_FEE_PER_BYTE, "Sweep Deposit")
	if (storageTX is not ''):
		addToUserBalance(username, newDepositDelta)
		balanceMBTC = satoshi_to_currency(getUserBalance(username), 'mbtc')
		AddEventString('Sweep Deposit successfully sent to storage: {} mBTC'.format(satoshi_to_currency(newDepositDelta, 'mbtc')))
		reddit.redditor(username).message('Your deposit was successful!', messageTemplates.USER_NEW_SWEEP_DEPOSIT_MESSAGE_TEXT.format(depositBalanceMBTC, depositBalanceMBTC, estimatedFeeMBTC, newDepositDeltaMBTC, balanceMBTC, storageTX))
	else:
		reddit.redditor(username).message('Your deposit was unuccessful!', messageTemplates.USER_FAILED_SWEEP_DEPOSIT_MESSAGE_TEXT.format(depositBalanceMBTC, depositBalanceMBTC, estimatedFeeMBTC, newDepositDeltaMBTC, balanceMBTC, storageTX))
		
	#  Return True so that we know to 
	return True

#  Process a withdrawal request, sending the bitcoin to their specified withdrawal address
def ProcessWithdraw(message, trueWithdrawal):
	username = message.author.name.lower()
	failedWithdrawalSubject = 'Failed Withdrawal'+('' if trueWithdrawal else ' Test')
	
	#  Split the message and grab the address and amount from it, if it is formatted correctly
	messageBody = message.body
	messageSplit = messageBody.partition(' ')
	withdrawalAddress = messageSplit[0]
	amountStringMBTC = messageSplit[2].upper()
	userBalance = getUserBalance(username)
	
	#  Allow the user to put ALL in as a value, and take the entire balance in that case
	if (amountStringMBTC == "ALL"):
		amountStringMBTC = satoshi_to_currency(userBalance, 'mbtc')
	
	#  Check that the address and amount are formatted correctly
	if ((GetAddressIsValid(withdrawalAddress) is False) or (amountStringMBTC.replace('.','',1).isdigit() is False)):
		AddEventString('Failed to withdraw \'{}\' to \'{}\''.format(amountStringMBTC, withdrawalAddress))
		reddit.redditor(username).message(failedWithdrawalSubject, messageTemplates.USER_FAILED_WITHDRAW_MESSAGE_TEXT.format(amountStringMBTC, withdrawalAddress))
		return False
		
	#  Check that the amount is above or equal to the minimum withdrawal
	amount = currency_to_satoshi_cached(amountStringMBTC, 'mbtc')
	amountMBTC = satoshi_to_currency(amount, 'mbtc')
	if (amount < botSpecificData.MINIMUM_WITHDRAWAL):
		AddEventString('/u/{} failed to withdraw \'{}\' mBTC (below minimum withdrawal value)'.format(username, amountMBTC))
		minimumWithdrawal = currency_to_satoshi_cached(botSpecificData.MINIMUM_WITHDRAWAL, 'mbtc')
		reddit.redditor(username).message(failedWithdrawalSubject, messageTemplates.USER_FAILED_WITHDRAW_BELOW_MINIMUM_MESSAGE_TEXT.format(amountMBTC, minimumWithdrawal))
		return False
		
	#  Check that the amount requested is in the user balance
	if (amount > userBalance):
		balanceMBTC = satoshi_to_currency(userBalance, 'mbtc')
		AddEventString('/u/{} failed to withdraw \'{}\' mBTC (insufficient balance of {})'.format(username, amountMBTC, balanceMBTC))
		reddit.redditor(username).message(failedWithdrawalSubject, messageTemplates.USER_FAILED_WITHDRAW_LOW_BALANCE_MESSAGE_TEXT.format(amountMBTC, balanceMBTC))
		return False
	
	AddEventString('Attempting to withdraw {} mBTC from storage. Storage balance: {}'.format(amountMBTC, storageKey.get_balance('mbtc')))
	
	#  Attempt to prepare the transaction so we can determine the fee
	estimatedFee = DetermineFee(storageKey, withdrawalAddress, amount, botSpecificData.WITHDRAWAL_FEE_PER_BYTE)
	estimatedFeeMBTC = satoshi_to_currency(estimatedFee, 'mbtc')
	
	#  If the fee is more than the amount, we can't transfer any bitcoin
	if (amount <= estimatedFee):
		AddEventString('/u/{} failed to withdraw \'{}\' (fee is greater than amount)'.format(username, amountMBTC))
		reddit.redditor(username).message(failedWithdrawalSubject, messageTemplates.USER_FAILED_WITHDRAW_FEE_TOO_HIGH_MESSAGE_TEXT.format(amount, estimatedFeeMBTC))
		return False
		
	#  If trueWithdrawal is False, we should just message the withdrawal data and not send the transaction
	if (trueWithdrawal is False):
		reddit.redditor(username).message('Withdrawal Test', messageTemplates.USER_WITHDRAWAL_TEST_MESSAGE_TEXT.format(amountMBTC, estimatedFeeMBTC))
		return False
	
	#  Now we should have an estimated fee, so we can subtract that from the amount we're sending, and transfer it
	AddEventString('Sending {} satoshis and paying {} satoshis for the fee'.format(amount, estimatedFee))
	if SendBitcoin(storageKey, withdrawalAddress, amount, estimatedFee, botSpecificData.WITHDRAWAL_FEE_PER_BYTE, "Basic Deposit"):
		amountMinusFees = amount - estimatedFee
		amountMinusFeeMBTC = satoshi_to_currency(amountMinusFees, 'mbtc')
		addToUserBalance(username, amount * -1)
		balanceMBTC = satoshi_to_currency(getUserBalance(username), 'mbtc')
		AddEventString('{} withdraw {} mBTC ({} + {} fee)'.format(username, amountMBTC, amountMinusFeeMBTC, estimatedFeeMBTC))
		reddit.redditor(username).message('Your withdrawal was successful!', messageTemplates.USER_SUCCESS_WITHDRAW_MESSAGE_TEXT.format(amountMBTC, amountMinusFeeMBTC, estimatedFeeMBTC, amountMBTC, balanceMBTC, storageTX))
		
	return True

#  Create a transaction we never send, in order to determine the transaction size and therefore the fee associated with it
def DetermineFee(senderKey, destinationAddress, amount, satoshisPerByte):
	try:
		#  Create a transaction (unsent), and figure out the transaction size in bytes
		storageTX = senderKey.create_transaction([(destinationAddress, amount, 'satoshi')], satoshisPerByte, destinationAddress)
		txSize = len(bytes.fromhex(storageTX))
		return satoshisPerByte * txSize
	except InsufficientFunds as ex: # Exception: "Balance 9999 is less than 10000 (including fee)"
		totalAfterFeeStr = str(ex).partition('less than ')[2].partition(' ')[0]
		return int(totalAfterFeeStr) - amount

#  Create and broadcast the bitcoin network transaction		
def SendBitcoin(senderKey, targetAddress, amount, estimatedFee, satoshisPerByte, transactionReason):
	amountMinusFee = amount - estimatedFee
	try:
		AddEventString('Sending {} satoshis'.format(amountMinusFee))
		tx = senderKey.send([(targetAddress, amountMinusFee, 'satoshi')], satoshisPerByte, STORAGE_ADDRESS)
		AddEventString('Transaction successful: {}'.format(tx))
		return tx
	except Exception as ex:
		amountMBTC = satoshi_to_currency(amount, 'mbtc')
		estimatedFeeMBTC = satoshi_to_currency(estimatedFee, 'mbtc')
		amountMinusFeeMBTC = satoshi_to_currency(satoshisPerByte, 'mbtc')
		AddEventString('{} transaction of {} mBTC failed ({} + {} fee)'.format(transactionReason, amountMBTC, amountMinusFeeMBTC, estimatedFeeMBTC))
		print("An exception of type {0} occurred.".format(type(ex).__name__))
		print(ex.args)
		return ""

#  Process a balance request from a user, letting them know their current balance
def ProcessBalance(username):
	#  If the user is not registered, inform them of this
	if (username not in userBalances):
		reddit.redditor(username).message('Balance Check', messageTemplates.USER_BALANCE_NOT_REGISTERED_MESSAGE_TEXT)
		return False
		
	balance = userBalances[username]
	balanceMBTC = satoshi_to_currency(balance, 'mbtc')
	reddit.redditor(username).message('Balance Check', messageTemplates.USER_BALANCE_MESSAGE_TEXT.format(balanceMBTC))
	AddEventString('User checked balance: {} [{} mBTC]'.format(username, balanceMBTC))
		
def GetAddressIsValid(address):
	try:
		balance = NetworkAPI.get_balance(address)
		return True
	except ConnectionError:
		return False
		
def GetAddressBalance(address):
	try:
		addressBalance = NetworkAPI.get_balance(address)
		return addressBalance
	except ConnectionError:
		AddEventString('Failed to get balance for address: {}'.format(address))
		return 0.0

#  Check the list of user deposit addresses
def processDeposits():
	for key in userKeyStructs:
		processSingleDeposit(key)
		
#  Check for solvency (add up tip balances, check against main storage
def checkSolvency():
	global userBalancesCopy
	global allTipBalanceTotal
	global storageBalance
	global solvencyDiff
	global lastSolvencyDiff
	
	allTipBalanceTotal = 0
	for user in userBalancesCopy: allTipBalanceTotal += userBalancesCopy[user]
		
	storageBalance = int(storageKey.get_balance())
		
	solvencyDiff = allTipBalanceTotal - storageBalance
	
	if (solvencyDiff != lastSolvencyDiff):
		lastSolvencyDiff = solvencyDiff
		AddEventString('Solvency report: Tip Balances [{}] - Storage [{}] = {}'.format(allTipBalanceTotal, storageBalance, lastSolvencyDiff), False)

#  If the deposit address for the given key has above the minimum balance of bitcoin in it, sweep the balance to storage and update the user's balance
def processSingleDeposit(username):
	global userDepositAddressesCopy
	senderKey = userKeyStructs[username]
	senderAddress = userDepositAddressesCopy[username]
	depositBalance = int(senderKey.get_balance())
	secondaryCheck = int(GetAddressBalance(senderAddress))
	
	#  If the amount in the wallet is empty or smaller than the minimum deposit value, there is no new deposit
	if (depositBalance <= botSpecificData.MINIMUM_DEPOSIT):
		return False
	
	#  If the two checks have different values, display an error and return out (this means money is transferring)
	if (depositBalance != secondaryCheck):
		AddEventString('Address {} balance check mismatch: ({} | {})'.format(senderAddress, depositBalance, secondaryCheck))
		return False
	
	#  Gather a list of unprocessed deposit transactions
	newDepositList = {}
	try:
		depositTransactionList = senderKey.get_transactions()
		if (depositTransactionList is ""):
			AddEventString("Could not load transaction list")
			return False
		
		for tx in depositTransactionList:
			if (tx in depositTransactionList):
				break
			else:
				newDepositList[tx] = depositTransactionList[tx]
	except json.decoder.JSONDecodeError:
		print("JSON decoding error when attempting to load transactions for {}".format(username))
		return False
	
	#  If we have no new deposits, we're just detecting already processed deposits and can ignore them
	if (len(newDepositList) == 0):
		return False
	
	depositBalanceMBTC = satoshi_to_currency(depositBalance, 'mbtc')
	AddEventString('Deposit detected in {}\'s account: {} mBTC'.format(username, depositBalanceMBTC))
	
	#  Attempt to prepare a transaction so we can determine the fee to take out so the user eats the cost
	estimatedFee = DetermineFee(senderKey, STORAGE_ADDRESS, depositBalance, botSpecificData.STORAGE_TRANSFER_FEE_PER_BYTE)
	
	#  Now we should have an estimated fee, so we can subtract that from the amount we're sending, and transfer it
	storageTX = SendBitcoin(senderKey, STORAGE_ADDRESS, depositBalance, estimatedFee, botSpecificData.STORAGE_TRANSFER_FEE_PER_BYTE, "Basic Deposit")
	if (storageTX is not ''):
		newDepositDelta = depositBalance - estimatedFee
		estimatedFeeMBTC = satoshi_to_currency(estimatedFee, 'mbtc')
		newDepositDeltaMBTC = satoshi_to_currency(newDepositDelta, 'mbtc')
		addToUserBalance(username, newDepositDelta)
		balanceMBTC = satoshi_to_currency(getUserBalance(username), 'mbtc')
		AddEventString('Deposit successfully sent to storage: {} mBTC'.format(newDepositDeltaMBTC))
		reddit.redditor(username).message('Your deposit was successful!', messageTemplates.USER_NEW_DEPOSIT_MESSAGE_TEXT.format(depositBalanceMBTC, depositBalanceMBTC, estimatedFeeMBTC, newDepositDeltaMBTC, balanceMBTC, storageTX))
		AddUserDepositTransaction(storageTX, username);
		
	
	#  Return True so that we know to remove this deposit from the queue
	return True

def getUserBalance(username):
	RegisterUser(username, False, True)
	return userBalances[username]
	
def addToUserBalance(username, amount, export=True):
	RegisterUser(username, False)
	userBalances[username] += amount
	if export:
		ExportUserBalancesJson()
	
def isBalanceSufficient(username, amount):
	if (getUserBalance(username) >= amount):
		return True
	else:
		return False
		
#  Process a single tip (only called on Successful Tip, so all data should be valid)
def processSingleTip(sender_name, target_name, amount):		
	if (isBalanceSufficient(sender_name, amount)):
		addToUserBalance(sender_name, amount * -1, False)
		addToUserBalance(target_name, amount)
		return True
	else:
		return False

def isUserRegistered(username):
	if (username in userBalances):
		return True
	else:
		return False
		
def RegisterUser(username, isMessage, quickReg=False):
	alreadyRegistered = False
	if (isUserRegistered(username)):
		alreadyRegistered = True
	else:
		CreateUserData(username)
		
	if quickReg:
		return True
	
	#  PM the registered user with their balance and deposit address. Mention if they were already registered and attempted to register by PM
	balance = getUserBalance(username)
	balanceMBTC = satoshi_to_currency(balance, 'mbtc')
	if (alreadyRegistered is True):
		if (isMessage is True):
			reddit.redditor(username).message('Registration', messageTemplates.USER_ALREADY_REGISTERED_REPLY_TEXT.format(balanceMBTC, userDepositAddresses[username], userDepositAddresses[username]))
	else:
		if (isMessage is True):
			reddit.redditor(username).message('Registration', messageTemplates.USER_NEW_REGISTRATION_REPLY_TEXT.format(balanceMBTC, userDepositAddresses[username], userDepositAddresses[username]))
		else:
			reddit.redditor(username).message('Registration', messageTemplates.USER_AUTO_REGISTRATION_MESSAGE_TEXT.format(balanceMBTC, userDepositAddresses[username], userDepositAddresses[username]))
	
	if (isMessage):
		AddEventString("Registration message processed: {} {}".format(username, ("(already registered)" if alreadyRegistered else "")))
	
#  Create the basic user, then export all of the data
def CreateUserData(username):
	userBalances[username] = 0
	userKeyStructs[username] = Key()
	userPrivateKeys[username] = userKeyStructs[username].to_wif()
	userDepositAddresses[username] = userKeyStructs[username].address
	ExportUserBalancesJson()
	ExportUserDepositAddressesJson()
	ExportUserPrivateKeysJson()
	
#  Add user transaction
def AddUserDepositTransaction(storageTX, username):
	userDepositTransactions[storageTX] = username
	ExportUserDepositTransactionsJson()
	
##  BALANCES EXPORT AND IMPORT
def ExportUserBalancesJson():
	with open('UserBalances.json', 'w') as f:
		json.dump(userBalances, f)

def ImportUserBalancesJson():
	if os.path.isfile("UserBalances.json"):
		with open("UserBalances.json", "rb") as f:
			balances = json.load(f)
			for balance in balances:
				userBalances[balance] = balances[balance]
		
##  DEPOSIT ADDRESSES EXPORT AND IMPORT
def ExportUserDepositAddressesJson():
	with open('UserDepositAddresses.json', 'w') as f:
		json.dump(userDepositAddresses, f)

def ImportUserDepositAddressesJson():
	if os.path.isfile("UserDepositAddresses.json"):
		with open("UserDepositAddresses.json", "rb") as f:
			addresses = json.load(f)
			for username in addresses:
				userDepositAddresses[username] = addresses[username]	
	
##  PRIVATE KEY EXPORT AND IMPORT
def ExportUserPrivateKeysJson():
	with open('UserPrivateKeys.json', 'w') as f:
		json.dump(userPrivateKeys, f)

def ImportUserPrivateKeysJson():
	if os.path.isfile("UserPrivateKeys.json"):
		with open("UserPrivateKeys.json", "rb") as f:
			usersToKeys = json.load(f)
			for username in usersToKeys:
				userPrivateKeys[username] = usersToKeys[username]
				userKeyStructs[username] = Key(userPrivateKeys[username])
				
##  USER DEPOSIT TRANSACTIONS EXPORT AND IMPORT
def ExportUserDepositTransactionsJson():
	with open('userDepositTransactions.json', 'w') as f:
		json.dump(userDepositTransactions, f)

def ImportUserDepositTransactionsJson():
	if os.path.isfile("userDepositTransactions.json"):
		with open("userDepositTransactions.json", "rb") as f:
			transactionsToUsers = json.load(f)
			for username in transactionsToUsers:
				userDepositTransactions[username] = transactionsToUsers[username]

if __name__ == '__main__':
    main()