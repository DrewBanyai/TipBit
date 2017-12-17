#  Reddit username of bot
BOT_USERNAME = 'ExampleBotName'

#  Array of subreddits which the bot should be allowed to comment in (does not reply to comments in other subs)
BOT_TEST_SUBS = ['ExampleSubredditName']

#  Dictionary of terms for amounts
AMOUNT_DICTIONARY = { 
	"pocketchange": "$0.5",
	"icecream": "$1",
	"coffee": "$3",
	"dinner": "$8",
	"dollar": "$1",
	"fiver": "$5",
	"tenspot": "$10",
	"jackson": "$20",
	"benjamin": "$100",
	}

#  Link to the page which explains how to use the bot
BOT_INTRO_LINK = 'http://example.explanation.URL'

#  The private key of the storage wallet (note that the private key provided with this code does not link to a wallet I actually use)
STORAGE_PRIVATE_KEY = 'EXAMPLE_PRIVATE_KEY'

#  Satoshis-Per-Byte for storage transfers transactions (from deposit address or from wallet being used for a sweep deposit)
STORAGE_TRANSFER_FEE_PER_BYTE = 21

#  Satoshis-Per-Byte for withdrawal transactions
WITHDRAWAL_FEE_PER_BYTE = 21

#  Minimum deposit in Satoshis 
MINIMUM_DEPOSIT = 50000 #  0.5 mBTC

#  Minimum withdrawal in Satoshis
MINIMUM_WITHDRAWAL = 50000 #  0.5 mBTC