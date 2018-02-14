import pycurl
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
	
import sys
import os
import time
import json
import botSpecificData
import string
from decimal import Decimal

#  BIT IMPORTS
from bit import Key, PrivateKey, PrivateKeyTestnet

# PRAW IMPORTS
import praw
from praw.models import Message
from praw.models import Comment
from prawcore.exceptions import RequestException

#  SEPARATED CODE IMPORTS
import messageTemplates
import botSpecificData
import tipbitUtilities
import tipbitWindow

#  Determine if this is the testnet or mainnet bot, then connect to the node via RPC
botSpecificData.DetermineDataBasedOnNetwork('testnet' in sys.argv)
tipbitUtilities.ConnectViaRPC()

reddit = praw.Reddit(botSpecificData.BOT_USERNAME)
BOT_MENTION = '/u/{}'.format(botSpecificData.BOT_USERNAME)

#  Initialize the existing user data dictionaries
userPrivateKeys = {}
userBalances = {}
userDepositAddressesLegacy = {}
userDepositAddressesSegwit = {}

primaryStorageBalance = 0
primaryTipBalance = 0
primarySolvencyDiff = 0
	
unreadMessages = []
unreadMessageCount = 0
unreadMentions = []
unreadMentionCount = 0
allUnread = []
markedRead = []
unsentTipFailures = []
unsentTipSuccesses = []
unsentCommentCount = 0

UnusedAddressesLegacy = []
UnusedAddressesSegwit = []
UsedAddressesLegacy = {}
UsedAddressesSegwit = {}

def ClaimPrimaryStorageAddresses():
	print('Claiming Primary Storage Addresses')
	tipbitUtilities.ImportPrivateKey(botSpecificData.PRIMARY_STORAGE_PRIVATE_KEY, 'PRIMARY STORAGE LEGACY' if botSpecificData.PRIMARY_STORAGE_SEGWIT else 'PRIMARY STORAGE', False)
	tipbitUtilities.GetNewSegwitAddress('PRIMARY STORAGE' if botSpecificData.PRIMARY_STORAGE_SEGWIT else 'PRIMARY STORAGE SEGWIT', botSpecificData.PRIMARY_STORAGE_ADDRESS_LEGACY, False)

def main():
	try:
		tipbitUtilities.ConsolePrint('- Bot ID: {}'.format(reddit.user.me()))
	except:
		tipbitUtilities.ConsolePrint("Failed to access PRAW. Shutting down")
		exit()
		
	#  Claim the primary storage address
	ClaimPrimaryStorageAddresses()

	#  Set up the GUI
	print('- Setting up GUI...')
	tipbitWindow.SetupGUI()
	
	#  Import user data and print the balances
	print('- Importing User Data...')
	ImportUserData()
	
	#  Gather a list of unused legacy and segwit addresses attached to this bitcoin wallet
	print('- Parsing existing addresses...')
	ParseExistingAddresses()
	
	#  Determine whether the connected node has the Primary Storage address controlled. If not, exit out
	if (CheckForPrimaryStorage() == False):
		print('Connected node does not have control over the Primary Storage address! Shutting down...')
		exit()
	
	#  Print out info about current balances
	print('')
	tipbitUtilities.PrintWalletBalancesList()
	print('')
	tipbitUtilities.PrintAccountBalancesList()
	print('')
	
	#  Initiate the main loop function
	print("- Initiating main loop")
	mainLoop()
	
def CheckForPrimaryStorage():
	accountsList = tipbitUtilities.GetAccountsList()
	for account in accountsList:
		addressList = tipbitUtilities.GetAddressListForAccount(account)
		for address in addressList:
			if (address == botSpecificData.PRIMARY_STORAGE_ADDRESS): return True
		
	return False

def processMessages():
	#  Hunt through the different subject lines we respond to. If it is anything else, toss it and mention it in console
	for message in unreadMessages:
		messageSubject = message.subject.upper()
		messageAuthor = message.author;
		messageAuthor = ('Name Unknown!' if (messageAuthor is None) else message.author.name.lower())
		
		if   (messageSubject == 'REGISTER'):			RegisterNewUser(messageAuthor, True)
		elif (messageSubject == 'SWEEP DEPOSIT'):		ProcessSweepDeposit(message)
		elif (messageSubject == 'WITHDRAW'):			ProcessWithdraw(message, True)
		elif (messageSubject == 'WITHDRAW TEST'):		ProcessWithdraw(message, False)
		elif (messageSubject == 'BALANCE'):				ProcessBalance(messageAuthor)
		else:											tipbitWindow.AddEventString("Removing unknown message: {}".format(message))
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
			tipbitWindow.AddEventString('We received a comment in another subreddit: {}'.format(subName))
		unreadMentions.remove(comment)

def processSingleComment(comment, commentBody):
	commentBody = commentBody.lower()
	if (commentBody == ''): return
	#  Note: This function allows you to pass in an altered comment body, which will then get processed. The comment reference is only used to reply onto
	
	#  Grab the author's name and post OP's name to use for tipping and registration purposes
	senderName = comment.author.name.lower()
	PostOPName = comment.submission.author.name.lower()
	
	#  If someone is trying to tip without being registered, comment on the failure and log the event
	if (isUserRegistered(senderName) is False):
		CommentReply_TipFailure(comment, messageTemplates.TIP_FAILURE_UNREGISTERED_USER.format(botSpecificData.BOT_REGISTER_PM_LINK), '')
		tipbitWindow.AddEventString('User {} failed to tip (sender not registered)'.format(senderName))
		return False
	
	#  Ensure that either the bot username is the beginning of the comment, or there is a space before it
	separate_around_bot = commentBody.partition(botSpecificData.BOT_USERNAME + ' ')
	if (separate_around_bot[1] != (botSpecificData.BOT_USERNAME + ' ')):
		tipbitWindow.AddEventString("Caught a comment reply with no mention. This shouldn't happen...")
		return
		
	#  Grab the different parts of the comment for later use
	separate_around_target = separate_around_bot[2].partition(" ")
	next_tip = separate_around_target[2].partition(botSpecificData.BOT_USERNAME + ' ')
	next_tip = (next_tip[1] + next_tip[2]) if (next_tip[1] == botSpecificData.BOT_USERNAME + ' ') else ''
			
	#  Figure out the target of this tip
	targetName = separate_around_target[0].lower()
	if ('/u/' in targetName):	targetName = targetName.partition('/u/')[2]
	if (targetName == 'op'): 	targetName = PostOPName
	print('processSingleComment() target: {}'.format(targetName))
	redditor = reddit.redditor(targetName)
	
	#  If this redditor isn't valid, comment on the failure and log the event
	if tipbitUtilities.isRedditorValid(redditor) is False:
		CommentReply_TipFailure(comment, messageTemplates.USERNAME_IS_REMOVED_OR_BANNED_TEXT.format(botSpecificData.BOT_USERNAME), targetName)
		tipbitWindow.AddEventString('Failed to tip {} (non-existent account)'.format(targetName))
		processSingleComment(comment, next_tip)
		return
		
	#  Grab the amount value string
	separate_around_amount = separate_around_target[2].partition(' ')
	if ('\n' in separate_around_amount[0]): separate_around_amount = separate_around_amount[0].partition('\n')
	amountString = separate_around_amount[0]
	
	#  Determine the amount in Satoshis. If the amount is invalid, comment on the failure and log the event
	amountSatoshi = getSatoshiFromAmountString(amountString)
	if amountSatoshi == -1:
		CommentReply_TipFailure(comment, messageTemplates.AMOUNT_NOT_SPECIFIED_TEXT, targetName)
		tipbitWindow.AddEventString('Failed to tip {} (unspecified amount: {})'.format(targetName, amountString))
		processSingleComment(comment, next_tip)
		return
		
	#  If the user does not have a sufficient balance to complete the tip, comment on the failure and log the event
	if (isBalanceSufficient(senderName, amountSatoshi) is False):
		CommentReply_TipFailure(comment, messageTemplates.AMOUNT_NOT_AVAILABLE_TEXT, targetName)
		tipbitWindow.AddEventString('Failed to tip {} (insufficient balance)'.format(targetName))
		processSingleComment(comment, next_tip)
		return

	#  If we get this far, the tip should be successful. Comment on the success, log it out, and complete the tip
	tipSuccess = True if (senderName is targetName) else processSingleTip(senderName, targetName, amountSatoshi)
	if (tipSuccess is True):
		tipbitWindow.AddEventString('Successful tip: {} -> {} ({})'.format(senderName, targetName, amountSatoshi))
		CommentReply_TipSuccess(comment, senderName, targetName, amountSatoshi, tipbitUtilities.SatoshisToUSD(amountSatoshi), botSpecificData.BOT_INTRO_LINK)
	else:
		tipbitWindow.AddEventString('Failed to tip: {} -> {} ({})'.format(senderName, targetName, amountSatoshi))
		CommentReply_TipFailure(comment, 'Unknown failure while tipping {}', targetName)
	
	#  Attempt to pass another tip from the same comment into this function to be processed
	processSingleComment(comment, next_tip)
		
def getSatoshiFromAmountString(amountString):
	if (tipbitUtilities.isStringFloat(amountString)):
		return int(tipbitUtilities.MBTCToSatoshis(Decimal(amountString)))
	if (amountString in botSpecificData.AMOUNT_DICTIONARY):
		return getSatoshiFromAmountString(botSpecificData.AMOUNT_DICTIONARY[amountString])
	if (amountString[0] == '$'):
		amountString = amountString[1:]
		if (tipbitUtilities.isStringFloat(amountString)):
			return int(tipbitUtilities.USDToSatoshis(amountString))
		
	return -1
		
#  Attempt to comment about the tip failure, and save off the comment if we fail to post it
def CommentReply_TipFailure(comment, commentTemplate, targetUsername, firstTry=True):
	try:
		comment.reply(commentTemplate.format(targetUsername))
		return True
	except praw.exceptions.APIException as ex:
		if (firstTry is True): 
			tipbitUtilities.ConsolePrint('Saving off tip failure comment due to exception: {}'.format(ex.error_type))
			failureComment = (comment, commentTemplate, targetUsername)
			unsentTipFailures.append(failureComment)
		return False
	except:
		tipbitWindow.AddEventString('Unknown error occurred while commenting on a successful tip...')
		return False
	
#  Attempt to comment about the tip success, and save off the comment if we fail to post it
def CommentReply_TipSuccess(comment, senderUsername, targetUsername, amountSatoshis, amountUSD, botInfoLink, firstTry=True):
	amountMBTC = tipbitUtilities.SatoshisToMBTC(amountSatoshis)
	try:
		comment.reply(messageTemplates.SUCCESSFUL_TIP_TEXT.format(senderUsername, targetUsername, amountMBTC, (' Testnet Bitcoins' if botSpecificData.testnet else ''), "%.2f" % amountUSD, botInfoLink))
		return True
	except praw.exceptions.APIException as ex:
		if (firstTry is True): 
			tipbitUtilities.ConsolePrint('Saving off tip success comment due to exception: {}'.format(ex.error_type))
			successComment = (comment, senderUsername, targetUsername, amountSatoshis, amountUSD, botInfoLink)
			unsentTipSuccesses.append(successComment)
		return False
	except:
		tipbitWindow.AddEventString('Unknown error occurred while commenting on a successful tip...')
		return False

#  Attempt to post any comments that failed to post the first time (generally due to reddit API restricting posting too many comments too quickly)
def processUnsent():
	unsentTipFailureCount = len(unsentTipFailures)
	unsentTipSuccessCount = len(unsentTipSuccesses)
	if (unsentTipSuccessCount == 0 and unsentTipSuccessCount == 0): return
	
	tipbitUtilities.ConsolePrint('Attempting to process unsent. [{} | {}]'.format(unsentTipFailureCount, unsentTipSuccessCount))

	while (len(unsentTipFailures) > 0):
		failure = unsentTipFailures[0]
		if (CommentReply_TipFailure(failure[0], failure[1], failure[2], False) is False): break
		tipbitWindow.AddEventString('Successfully sent a previously blocked comment')
		unsentTipFailures.remove(failure)
		
	while len(unsentTipSuccesses) > 0:
		success = unsentTipSuccesses[0]
		if (CommentReply_TipSuccess(success[0], success[1], success[2], success[3], success[4], success[5], False) is False): break
		tipbitWindow.AddEventString('Successfully sent a previously blocked comment')
		unsentTipSuccesses.remove(success)

#  Process a sweep deposit, pushing money from a wallet with the given private key to our storage (to avoid the double transaction fee you get when using the normal deposit method)
def ProcessSweepDeposit(message):
	username = message.author.name.lower()
	userAccount = reddit.redditor(username)
	RegisterNewUser(username, False)
	
	tipbitWindow.AddEventString('Attempting Sweep Deposit: {}'.format(message.body))
	if (tipbitUtilities.ImportPrivateKey(message.body, '', True) is False):
		print('Failed to sweep private key "{}"'.format(message.body))
		return
	
	legacyAddress = PrivateKeyTestnet(message.body).address if botSpecificData.testnet else PrivateKey(message.body).address
	print('legacy sweep - {}'.format(legacyAddress))
	segwitAddress = tipbitUtilities.GetUnusedAddressSegwit('', legacyAddress)
	print('segwit sweep - {}'.format(segwitAddress))
	
	sweepAddress = ''
	balanceList = tipbitUtilities.GetWalletBalancesList()
	if 		(legacyAddress in balanceList): 	sweepAddress = legacyAddress
	elif 	(segwitAddress in balanceList): 	sweepAddress = segwitAddress
	
	if (sweepAddress == ''):
		print('Attempted sweep of empty wallet. Cancelling Sweep Deposit for {}'.format(username))
		return
	
	print('Balance found at sweep address: {}'.format(sweepAddress))
	sweepBalance = tipbitUtilities.BTCToSatoshis(balanceList[sweepAddress])
	
	print('Sweep Balance: {} Satoshis'.format(sweepBalance))

	if (sweepBalance < botSpecificData.MINIMUM_DEPOSIT):
		MINIMUM_DEPOSIT_MBTC = tipbitUtilities.SatoshisToMBTC(botSpecificData.MINIMUM_DEPOSIT)
		tipbitWindow.AddEventString('Failed to perform sweep deposit for user [{}] (balance under minimum deposit)'.format(username))
		userAccount.message('Sweep Deposit failed!', messageTemplates.USER_FAILED_SWEEP_DEPOSIT_UNDER_MINIMUM_MESSAGE_TEXT.format(MINIMUM_DEPOSIT_MBTC, (' Testnet Bitcoins' if botSpecificData.testnet else '')))
		return False

	#  Attempt to prepare a transaction so we can determine the fee to take out so the user eats the cost
	depositBalance = sweepBalance
	storageTX = ''
	estimatedFee, storageTX = tipbitUtilities.SendFromAddressToAddress(sweepAddress, botSpecificData.PRIMARY_STORAGE_ADDRESS, depositBalance, botSpecificData.STORAGE_TRANSFER_FEE_PER_BYTE)
	newDepositDelta = depositBalance - estimatedFee
	
	depositBalanceMBTC = tipbitUtilities.SatoshisToMBTC(depositBalance)
	estimatedFeeMBTC = tipbitUtilities.SatoshisToMBTC(estimatedFee)
	newDepositDeltaMBTC = tipbitUtilities.SatoshisToMBTC(newDepositDelta)
	
	#  Now we should have an estimated fee, so we can subtract that from the amount we're sending, and transfer it
	addToUserBalance(username, int(newDepositDelta))
	balanceMBTC = tipbitUtilities.SatoshisToMBTC(getUserBalance(username))
	tipbitWindow.AddEventString('Sweep Deposit successfully sent to storage: {} mBTC{}'.format(tipbitUtilities.SatoshisToMBTC(newDepositDelta), (' Testnet Bitcoins' if botSpecificData.testnet else '')))
	userAccount.message('Your deposit was successful!', messageTemplates.USER_NEW_SWEEP_DEPOSIT_MESSAGE_TEXT.format(depositBalanceMBTC, (' Testnet Bitcoins' if botSpecificData.testnet else ''), depositBalanceMBTC, estimatedFeeMBTC, newDepositDeltaMBTC, balanceMBTC, (' Testnet Bitcoins' if botSpecificData.testnet else ''), storageTX))

	tipbitUtilities.SetAddressToAccount(legacyAddress, '')
	tipbitUtilities.SetAddressToAccount(segwitAddress, '')
	
	#  Return True so that we know to 
	return True

#  Process a withdrawal request, sending the bitcoin to their specified withdrawal address
def ProcessWithdraw(message, trueWithdrawal):
	global primaryStorageBalance
	username = message.author.name.lower()
	
	#  Split the message and grab the address and amount from it, if it is formatted correctly
	messageBody = message.body
	messageSplit = messageBody.partition(' ')
	withdrawalAddress = messageSplit[0]
	amountStringMBTC = messageSplit[2].upper()
	userBalance = getUserBalance(username)
	
	#  Allow the user to put ALL in as a value, and take the entire balance in that case
	if (amountStringMBTC == 'ALL'):
		amountStringMBTC = tipbitUtilities.SatoshisToMBTC(userBalance)
		
	print('User {} attempting to withdraw {}'.format(username, amountStringMBTC))
	
	#  Check that the address and amount are formatted correctly
	if (isinstance(amountStringMBTC, str) and amountStringMBTC.replace('.','',1).isdigit() is False):
		failedWithdrawalSubject = 'Failed Withdrawal' + ('' if trueWithdrawal else ' Test')
		tipbitWindow.AddEventString('Failed to withdraw \'{}\' to \'{}\''.format(amountStringMBTC, withdrawalAddress))
		reddit.redditor(username).message(failedWithdrawalSubject, messageTemplates.USER_FAILED_WITHDRAW_MESSAGE_TEXT.format(amountStringMBTC, withdrawalAddress))
		return False
		
	#  Check that the amount is above or equal to the minimum withdrawal
	amount = tipbitUtilities.MBTCToSatoshis(Decimal(amountStringMBTC))
	amountMBTC = tipbitUtilities.SatoshisToMBTC(amount)
	if (amount < botSpecificData.MINIMUM_WITHDRAWAL):
		tipbitWindow.AddEventString('/u/{} failed to withdraw \'{}\' mBTC (below minimum withdrawal value)'.format(username, amountMBTC))
		reddit.redditor(username).message(failedWithdrawalSubject, messageTemplates.USER_FAILED_WITHDRAW_BELOW_MINIMUM_MESSAGE_TEXT.format(amountMBTC, (' Testnet Bitcoins' if botSpecificData.testnet else ''), botSpecificData.MINIMUM_WITHDRAWAL, (' Testnet Bitcoins' if botSpecificData.testnet else '')))
		return False
		
	#  Check that the amount requested is in the user balance
	if (amount > userBalance):
		balanceMBTC = tipbitUtilities.SatoshisToMBTC(userBalance)
		tipbitWindow.AddEventString('/u/{} failed to withdraw \'{}\' mBTC (insufficient balance of {})'.format(username, amountMBTC, balanceMBTC))
		reddit.redditor(username).message(failedWithdrawalSubject, messageTemplates.USER_FAILED_WITHDRAW_LOW_BALANCE_MESSAGE_TEXT.format(amountMBTC, (' Testnet Bitcoins' if botSpecificData.testnet else ''), balanceMBTC, (' Testnet Bitcoins' if botSpecificData.testnet else '')))
		return False
	
	tipbitWindow.AddEventString('Attempting to withdraw {} mBTC. Storage balance: {} satoshis'.format(amountMBTC, primaryStorageBalance))
	
	#  Attempt to prepare the transaction so we can determine the fee
	sentTX = ''
	estimatedFee, sentTX = tipbitUtilities.SendFromAddressToAddress(botSpecificData.PRIMARY_STORAGE_ADDRESS, withdrawalAddress, tipbitUtilities.SatoshisToBTC(amount), botSpecificData.WITHDRAWAL_FEE_PER_BYTE, True)
	estimatedFeeMBTC = tipbitUtilities.SatoshisToMBTC(estimatedFee)
	
	#  If the fee is more than the amount, we can't transfer any bitcoin
	if (amount <= estimatedFee):
		tipbitWindow.AddEventString('/u/{} failed to withdraw \'{}\' (fee is greater than amount)'.format(username, amountMBTC))
		reddit.redditor(username).message(failedWithdrawalSubject, messageTemplates.USER_FAILED_WITHDRAW_FEE_TOO_HIGH_MESSAGE_TEXT.format(amount, (' Testnet Bitcoins' if botSpecificData.testnet else ''), estimatedFeeMBTC, (' Testnet Bitcoins' if botSpecificData.testnet else '')))
		return False
		
	#  If trueWithdrawal is False, we should just message the withdrawal data and not send the transaction
	if (trueWithdrawal is False):
		reddit.redditor(username).message('Withdrawal Test', messageTemplates.USER_WITHDRAWAL_TEST_MESSAGE_TEXT.format(amountMBTC, (' Testnet Bitcoins' if botSpecificData.testnet else ''), estimatedFeeMBTC, (' Testnet Bitcoins' if botSpecificData.testnet else '')))
		return False
	
	#  Now we should have an estimated fee, so we can subtract that from the amount we're sending, and transfer it
	tipbitWindow.AddEventString('Sending {} satoshis and paying {} satoshis for the fee'.format(amount, estimatedFee))
	result, sentTX = tipbitUtilities.SendFromAddressToAddress(botSpecificData.PRIMARY_STORAGE_ADDRESS, withdrawalAddress, tipbitUtilities.SatoshisToBTC(amount - estimatedFee), botSpecificData.WITHDRAWAL_FEE_PER_BYTE)
	print('Withdrawal result: {}'.format(result)) #  TODO: Test failed withdrawal due to bad address
	
	amountMinusFees = amount - estimatedFee
	amountMinusFeeMBTC = tipbitUtilities.SatoshisToMBTC(amountMinusFees)
	addToUserBalance(username, amount * -1)
	balanceMBTC = tipbitUtilities.SatoshisToMBTC(getUserBalance(username))
	tipbitWindow.AddEventString('{} withdrew {} mBTC {}({} + {} fee)'.format(username, amountMBTC, (' Testnet Bitcoins' if botSpecificData.testnet else ''), amountMinusFeeMBTC, estimatedFeeMBTC))
	reddit.redditor(username).message('Your withdrawal was successful!', messageTemplates.USER_SUCCESS_WITHDRAW_MESSAGE_TEXT.format(amountMBTC, estimatedFeeMBTC, amountMinusFeeMBTC, balanceMBTC, (' Testnet Bitcoins' if botSpecificData.testnet else '')))
		
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
		tipbitWindow.AddEventString('Sending {} Satoshis'.format(amountMinusFee))
		tx = senderKey.send([(targetAddress, amountMinusFee, 'satoshi')], satoshisPerByte, botSpecificData.PRIMARY_STORAGE_ADDRESS)
		tipbitWindow.AddEventString('Transaction successful: {}'.format(tx))
		return tx
	except Exception as ex:
		amountMBTC = tipbitUtilities.SatoshisToMBTC(amount)
		estimatedFeeMBTC = tipbitUtilities.SatoshisToMBTC(estimatedFee)
		amountMinusFeeMBTC = tipbitUtilities.SatoshisToMBTC(satoshisPerByte)
		tipbitWindow.AddEventString('{} transaction of {} mBTC failed ({} + {} fee)'.format(transactionReason, amountMBTC, amountMinusFeeMBTC, estimatedFeeMBTC))
		tipbitUtilities.ConsolePrint("An exception of type {0} occurred.".format(type(ex).__name__))
		tipbitUtilities.ConsolePrint(ex.args)
		return ""

#  Process a balance request from a user, letting them know their current balance
def ProcessBalance(username):
	#  If the user is not registered, inform them of this
	if (username not in userBalances):
		reddit.redditor(username).message('Balance Check', messageTemplates.USER_BALANCE_NOT_REGISTERED_MESSAGE_TEXT.format(botSpecificData.BOT_REGISTER_PM_LINK))
		return False
		
	balance = userBalances[username]
	balanceMBTC = tipbitUtilities.SatoshisToMBTC(balance)
	reddit.redditor(username).message('Balance Check', messageTemplates.USER_BALANCE_MESSAGE_TEXT.format(balanceMBTC, (' Testnet Bitcoins' if botSpecificData.testnet else ''), userDepositAddressesSegwit[username], userDepositAddressesSegwit[username], userDepositAddressesLegacy[username], userDepositAddressesLegacy[username]))
	tipbitWindow.AddEventString('User checked balance: {} [{} mBTC{}]'.format(username, balanceMBTC, (' Testnet Bitcoins' if botSpecificData.testnet else '')))
		
##### UTILITIES
		
def ParseExistingAddresses():
	tipbitUtilities.ClaimExistingUserAddresses(userPrivateKeys, userDepositAddressesLegacy, userDepositAddressesSegwit)
	tipbitUtilities.ExportUserDepositAddressesSegwitJson(userDepositAddressesSegwit)
	
	tipbitUtilities.SaveOffUnusedAddresses(UnusedAddressesLegacy, UnusedAddressesSegwit)
	tipbitUtilities.SaveOffUsedAddresses(UsedAddressesLegacy, UsedAddressesSegwit)

def getUserBalance(username):
	if not isUserRegistered(username): RegisterNewUser(username, False, True)
	return userBalances[username]
	
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
	
def addToUserBalance(username, satoshis, export = True):
	if not isUserRegistered(username): RegisterNewUser(username, False, True)
	userBalances[username] += int(satoshis)
	
	if export:
		tipbitUtilities.ExportUserBalancesJson(userBalances)
		
	return userBalances[username]
	
def isUserRegistered(username):
	return (username in userBalances)
	
def RegisterNewUser(username, isMessage, quickReg=False):
	username = username.lower()
	alreadyRegistered = isUserRegistered(username)
	if alreadyRegistered is False: CreateUserData(username)
	
	balance = getUserBalance(username)
	balanceMBTC = tipbitUtilities.SatoshisToMBTC(balance)
	
	if ((alreadyRegistered is False) and (isMessage is False)):
		reddit.redditor(username).message('Registration', messageTemplates.USER_AUTO_REGISTRATION_MESSAGE_TEXT.format(userDepositAddressesSegwit[username], userDepositAddressesSegwit[username], userDepositAddressesLegacy[username], userDepositAddressesLegacy[username]))
		
	if quickReg:
		return True
	
	#  PM the registered user with their balance and deposit address. Mention if they were already registered and attempted to register by PM
	balance = getUserBalance(username)
	balanceMBTC = tipbitUtilities.SatoshisToMBTC(balance)
	if (isMessage is True):
		tipbitWindow.AddEventString("Registration message processed: {} {}".format(username, ("(already registered)" if alreadyRegistered else "")))
		if (alreadyRegistered is True):
			reddit.redditor(username).message('Registration', messageTemplates.USER_ALREADY_REGISTERED_REPLY_TEXT.format(userDepositAddressesSegwit[username], userDepositAddressesSegwit[username], userDepositAddressesLegacy[username], userDepositAddressesLegacy[username]))
		else:
			reddit.redditor(username).message('Registration', messageTemplates.USER_NEW_REGISTRATION_REPLY_TEXT.format(userDepositAddressesSegwit[username], userDepositAddressesSegwit[username], userDepositAddressesLegacy[username], userDepositAddressesLegacy[username]))
	
#  Create the basic user, then export all of the data
def CreateUserData(username):
	username = username.lower()
	newAddressLegacy = tipbitUtilities.GetUnusedAddressLegacy(UnusedAddressesLegacy, username)
	newAddressSegwit = tipbitUtilities.GetUnusedAddressSegwit(username + ' Segwit', newAddressLegacy)
	
	userBalances[username] = 0
	userDepositAddressesLegacy[username] = newAddressLegacy
	userDepositAddressesSegwit[username] = newAddressSegwit
	userPrivateKeys[username] = tipbitUtilities.GetPrivateKeyFromAddress(newAddressLegacy)
	
	tipbitUtilities.ExportUserBalancesJson(userBalances)
	tipbitUtilities.ExportUserDepositAddressesLegacyJson(userDepositAddressesLegacy)
	tipbitUtilities.ExportUserDepositAddressesSegwitJson(userDepositAddressesSegwit)
	tipbitUtilities.ExportUserPrivateKeysJson(userPrivateKeys)
	
	print('Registered {}:'.format(username))
	print(' - Legacy: {}'.format(newAddressLegacy))
	print(' - Segwit: {}'.format(newAddressSegwit))
	
##### PythonRPC Primary Code

def ImportUserData():
	tipbitUtilities.ImportUserBalancesJson(userBalances, True)
	tipbitUtilities.ImportUserDepositAddressesLegacyJson(userDepositAddressesLegacy)
	tipbitUtilities.ImportUserDepositAddressesSegwitJson(userDepositAddressesSegwit)
	tipbitUtilities.ImportUserPrivateKeysJson(userPrivateKeys)

def CheckForUserDeposits():
	global primaryStorageBalance
	walletBalances = tipbitUtilities.GetWalletBalancesList()
	addressToAccounts = tipbitUtilities.GetAddressToAccountList()
	
	for wallet in walletBalances:
		if wallet == botSpecificData.PRIMARY_STORAGE_ADDRESS:
			primaryStorageBalance = tipbitUtilities.BTCToSatoshis(walletBalances[wallet])
			continue
			
		if wallet not in addressToAccounts: continue
		if addressToAccounts[wallet] == '': continue
		
		# Get the account name (take out ' Segwit' if it exists)
		accountName = addressToAccounts[wallet]
		account = accountName[:-7] if (' Segwit' in accountName) else accountName
		userAccount = reddit.redditor(account)
		
		walletBalance = walletBalances[wallet]
		walletBalanceSatoshis = tipbitUtilities.BTCToSatoshis(walletBalance)
		if (walletBalanceSatoshis < botSpecificData.MINIMUM_DEPOSIT): continue
		
		print('Wallet balance detected: {} ({})'.format(account, walletBalance))
		
		sentTX = ''
		fee, sentTX = tipbitUtilities.SendFromAddressToAddress(wallet, botSpecificData.PRIMARY_STORAGE_ADDRESS, walletBalance, botSpecificData.STORAGE_TRANSFER_FEE_PER_BYTE)
		walletBalanceSatoshis = tipbitUtilities.BTCToSatoshis(walletBalances[wallet])
		print('Sent {} satoshis with fee of {} satoshis to Storage'.format(walletBalanceSatoshis - fee, fee))
		
		balanceDelta = walletBalanceSatoshis - fee
		userBalances[account] += int(balanceDelta)
		print('Updated User Balance ({} + {}): {}\n'.format(account, balanceDelta,  userBalances[account]))
		
		depositBalanceMBTC = tipbitUtilities.SatoshisToMBTC(walletBalanceSatoshis)
		estimatedFeeMBTC = tipbitUtilities.SatoshisToMBTC(fee)
		newDepositDeltaMBTC = depositBalanceMBTC - estimatedFeeMBTC
		balanceMBTC = tipbitUtilities.SatoshisToMBTC(userBalances[account])
		userAccount.message('Your deposit was successful!', messageTemplates.USER_NEW_DEPOSIT_MESSAGE_TEXT.format(depositBalanceMBTC, (' Testnet Bitcoins' if botSpecificData.testnet else ''), depositBalanceMBTC, estimatedFeeMBTC, newDepositDeltaMBTC, balanceMBTC, (' Testnet Bitcoins' if botSpecificData.testnet else ''), sentTX))
		
		tipbitUtilities.ExportUserBalancesJson(userBalances)
		
		UpdateGUI()
	
	
def UpdateBalancesAndSolvency():
	global primaryStorageBalance
	global primaryTipBalance
	global primarySolvencyDiff
	
	walletBalances = tipbitUtilities.GetWalletBalancesList()
	if len(walletBalances) == 0:
		print('GetWalletBalanceList() failed to return a list (connection error?). Skipping solvency check...')
		return
	
	if (botSpecificData.PRIMARY_STORAGE_ADDRESS not in walletBalances):
		tipbitUtilities.ImportPrivateKey(botSpecificData.PRIMARY_STORAGE_PRIVATE_KEY, 'PRIMARY STORAGE LEGACY' if botSpecificData.segwit else 'PRIMARY STORAGE', True)
		tipbitUtilities.GetNewSegwitAddress('PRIMARY STORAGE' if botSpecificData.segwit else 'PRIMARY STORAGE SEGWIT', botSpecificData.PRIMARY_STORAGE_ADDRESS_LEGACY)
			
	primaryStorageBalance = tipbitUtilities.BTCToSatoshis(walletBalances[botSpecificData.PRIMARY_STORAGE_ADDRESS])
	
	primaryTipBalance = 0
	for user in userBalances: primaryTipBalance += userBalances[user]
	
	primarySolvencyDiff = 0
	if (primaryTipBalance != primaryStorageBalance): primarySolvencyDiff = primaryTipBalance - primaryStorageBalance
		
def UpdateGUI():
	global primaryStorageBalance
	global primaryTipBalance
	global primarySolvencyDiff
	
	UpdateBalancesAndSolvency()
	tipbitWindow.SetGUITipBalanceString(primaryTipBalance)
	tipbitWindow.SetGUIStorageBalanceString(primaryStorageBalance)
	tipbitWindow.SetGUISolvencyDiffString(primarySolvencyDiff)
		
def mainLoop():
	currentTime = time.time()
	lastMainLoopTime 		= currentTime
	lastUnsentCheckTime 	= currentTime
	lastSolvencyCheckTime 	= currentTime
	lastDepositCheckTime 	= currentTime
	lastBitcoinValueTime 	= currentTime
	lastUpdateGUITime 		= currentTime
	
	global storageListbox
	global depositsListbox
	
	global userBalancesCopy
	global userDepositAddressesCopy
	solvencyThread = 0
	depositsThread = 0
	
	while (True):
		try:
			currentTime = time.time()
				
			#  Get the latest bitcoin price
			if (currentTime > lastBitcoinValueTime):
				tipbitUtilities.GetBitcoinValue(True, primaryTipBalance)
				lastBitcoinValueTime = currentTime + 1800.0
			
			#  Check for the ESCAPE key, Balance Key (b), and Space Key (spacebar)
			tipbitUtilities.checkForInput(userBalances)
			
			#  Update the window's processing loop and process the event queue
			tipbitWindow.ProcessEventQueue()
			tipbitWindow.UpdateWindow()
				
			#  Run the main loop every 3.0 seconds
			if (currentTime < lastMainLoopTime): continue
			lastMainLoopTime = currentTime + 3.0
					
			#  Collect all unread mentions and messages
			gatherUnreads()
			
			#  Display any change in the current unread or unsent count
			displayUnreadUnsentCount()
			
			#  Attempt to re-post comments that failed to post if at least 10 seconds has gone by
			if (currentTime > lastUnsentCheckTime):
				processUnsent()
				lastUnsentCheckTime = currentTime + 10.0
			
			#  Check the next 5 messages
			processMessages()
			
			#  Check the next 5 comments
			processComments()
			
			#  Check for user deposits and send them to Storage after crediting account
			CheckForUserDeposits()
			
			#  Update the GUI with user balance, storage total, solvency diff, and any events that have transpired
			UpdateGUI()
			
		except ConnectionError:
			tipbitWindow.AddEventString("ConnectionError occurred during processing...", False)
		except RequestException:
			tipbitWindow.AddEventString('RequestException on processing unreads (likely a connection error)', False)
	
#  Gather all unread messages and comments, checking for exceptions along the way (particularly the ones common when using PRAW)
def gatherUnreads():
	global allUnread
	global markedRead
	allUnread = reddit.inbox.unread(limit=1)
	try:
		for item in allUnread:
			if (item in markedRead):
				tipbitWindow.AddEventString("reddit.inbox.unread is returning items after they're marked read... something is wrong")
				continue
			try:
				if isinstance(item, Message):
					unreadMessages.append(item)
				elif isinstance(item, Comment):
					unreadMentions.append(item)
			except urllib3.exceptions.ReadTimeoutError:
				tipbitWindow.AddEventString('ReadTimeoutError on processing of unread messages and comments...')
			except ssl.SSLError:
				tipbitWindow.AddEventString('SSL error on processing of unread messages and comments...')
			except Exception as e:
				tipbitUtilities.ConsolePrint(e)
				tipbitWindow.AddEventString('Unknown exception on processing of unread messages and comments...')
	except RequestException:
		tipbitWindow.AddEventString('RequestException on processing unreads (likely a connection error)', False)
	
	for item in unreadMessages: markedRead.append(item)
	for item in unreadMentions: markedRead.append(item)
	reddit.inbox.mark_read(unreadMessages)
	reddit.inbox.mark_read(unreadMentions)
	
#  Display the current count of mentions, messages, and comments
def displayUnreadUnsentCount():
	global unreadMentionCount
	global unreadMessageCount
	global unsentCommentCount
	if ((len(unreadMentions) is not unreadMentionCount) or (len(unreadMessages) is not unreadMessageCount) or ((len(unsentTipFailures) + len(unsentTipSuccesses)) is not unsentCommentCount)):
		tipbitUtilities.ConsolePrint("Comments / Messages / Unsent: [{}, {}, {}]".format(len(unreadMentions), len(unreadMessages), (len(unsentTipFailures) + len(unsentTipSuccesses))))
	unreadMentionCount = len(unreadMentions)
	unreadMessageCount = len(unreadMessages)
	unsentCommentCount = len(unsentTipFailures) + len(unsentTipSuccesses)
	
	
##### 

if __name__ == '__main__':
    main()