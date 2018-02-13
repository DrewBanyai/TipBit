#  Whether this is the testnet or mainnet bot
testnet = True

#  Whether or not Primary Storage utilizes Segwit
PRIMARY_STORAGE_SEGWIT = True

#  Reddit username of bot and developer
BOT_USERNAME = 'UNKNOWN'
DEVELOPER_USERNAME = 'YOUR_REDDIT_USERNAME_HERE'

#  Array of subreddits which the bot should be allowed to comment in (does not reply to comments in other subs)
BOT_TEST_SUBS = [] #  UNKNOWN UNTIL DetermineDataBasedOnNetwork

#  Dictionary of terms for amounts
AMOUNT_DICTIONARY = { 
	"pocketchange": "$0.5",
	"icecream": "$1",
	"beer": "$2",
	"coffee": "$3",
	"dinner": "$8",
	"dollar": "$1",
	"fiver": "$5",
	"tenspot": "$10",
	"jackson": "$20",
	"benjamin": "$100",
	}

#  Link to the page which explains how to use the bot
BOT_INTRO_LINK = 'UNKNOWN' #  UNKNOWN UNTIL DetermineDataBasedOnNetwork
BOT_REGISTER_PM_LINK = 'UNKNOWN' #  UNKNOWN UNTIL DetermineDataBasedOnNetwork
BOT_DEV_CONTACT_LINK = 'https://www.reddit.com/message/compose?to={}&subject=Question&message=I%20have%20a%20question.'.format(DEVELOPER_USERNAME)

#  The primary storage address (where all coins are held while in use, until withdrawn)
PRIMARY_STORAGE_PRIVATE_KEY 	= 'UNKNOWN' #  UNKNOWN UNTIL DetermineDataBasedOnNetwork
PRIMARY_STORAGE_ADDRESS 		= 'UNKNOWN' #  UNKNOWN UNTIL DetermineDataBasedOnNetwork
PRIMARY_STORAGE_ADDRESS_LEGACY 	= 'UNKNOWN' #  UNKNOWN UNTIL DetermineDataBasedOnNetwork

#  Satoshis-Per-Byte for storage transfers transactions (from deposit address or from wallet being used for a sweep deposit)
STORAGE_TRANSFER_FEE_PER_BYTE = 30

#  Satoshis-Per-Byte for withdrawal transactions
WITHDRAWAL_FEE_PER_BYTE = 30

#  Minimum deposit in Satoshis 
MINIMUM_DEPOSIT = 100000 #  1 mBTC

#  Minimum withdrawal in Satoshis
MINIMUM_WITHDRAWAL = 100000 #  1 mBTC

#  Personal node data
rpc_user = 'YOUR_RPC_USERNAME_HERE'
rpc_password = 'YOUR_RPC_PASSWORD_HERE'
port = 'UNKNOWN' #  UNKNOWN UNTIL DetermineDataBasedOnNetwork

def DetermineDataBasedOnNetwork(test_network):
	global testnet
	global port
	global BOT_USERNAME
	global BOT_TEST_SUBS
	global BOT_INTRO_LINK
	global BOT_REGISTER_PM_LINK
	global PRIMARY_STORAGE_PRIVATE_KEY
	global PRIMARY_STORAGE_ADDRESS
	global PRIMARY_STORAGE_ADDRESS_LEGACY
	
	testnet = test_network
	print('Network: {}'.format('TESTNET' if testnet else 'MAINNET'))
	
	BOT_USERNAME = 'YOUR_TESTBOT_REDDIT_USERNAME_HERE' if testnet else 'YOUR_MAINBOT_REDDIT_USERNAME_HERE'
	port = ('18332' if testnet else '8332')
	
	BOT_TEST_SUBS = ['subname', 'othersubname'] if testnet else ['subname', 'othersubname']
	BOT_INTRO_LINK = 'TEST_BOT_INTRO_LINK' if testnet else 'MAIN_BOT_INTRO_LINK'
	BOT_REGISTER_PM_LINK = 'https://www.reddit.com/message/compose?to={}&subject=Register&message=Please%20register%20my%20reddit%20account'.format(BOT_USERNAME)
	
	PRIMARY_STORAGE_PRIVATE_KEY = 'TESTNET_STORAGE_PRIVATE_KEY' if testnet else 'MAINNET_STORAGE_PRIVATE_KEY'
	
	if PRIMARY_STORAGE_SEGWIT:
		PRIMARY_STORAGE_ADDRESS_LEGACY = ('TESTNET_LEGACY_PRIMARY_STORAGE_ADDRESS') if testnet else ('MAINNET_LEGACY_PRIMARY_STORAGE_ADDRESS')
		PRIMARY_STORAGE_ADDRESS = ('TESTNET_SEGWIT_PRIMARY_STORAGE_ADDRESS') if testnet else ('MAINNET_SEGWIT_PRIMARY_STORAGE_ADDRESS')
	else:
		PRIMARY_STORAGE_ADDRESS = ('TESTNET_LEGACY_PRIMARY_STORAGE_ADDRESS') if testnet else ('MAINNET_LEGACY_PRIMARY_STORAGE_ADDRESS')
		PRIMARY_STORAGE_ADDRESS_LEGACY = PRIMARY_STORAGE_ADDRESS
	
	print('Primary Storage: {}'.format(PRIMARY_STORAGE_ADDRESS))