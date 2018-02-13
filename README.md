# TipBit

TipBit is a functional Bitcoin tip-bot for Reddit. With a simple setup, you can run a bot that will allow users to register, deposit, tip, check their balance, and withdraw all through messages and comments. This allows off-chain movement of bitcoin and promotes a sharing culture within the reddit Bitcoin community.

## Getting Started

Grab a copy of the repository, and open up botSpecificData.py to set your own variables. Set BOT_USERNAME to the reddit username your bot will control. Fill in the array BOT_TEST_SUBS with the subreddits you want your bot to be able to reply in (it is unwise to let him go everywhere, as some subreddits don't like bots). You'll want to set BOT_INTRO_LINK to a string of the URL to a page explaining your bot. If you don't know how to use a bitcoin wallet yet, you should probably understand that all first before trying the bot. If you do understand it already, grab the public address of the wallet you want to use for storage, and set the PRIMARY_STORAGE_ADDRESS to that string. You can set the fee variables and minimum value variables to whatever you feel is appropriate. Lastly, you need to set the login information for your local Bitcoin Core RPC calls.

Find a tutorial on creating a reddit bot real quick to get instructions on how to set up your "app" in reddit, as that is beyond the scope of this project. You'll want to edit the praw.ini file with your information, but any reddit python bot tutorial should explain that clearly enough for anyone, so I'll leave that out of here as well. Once that's set up, run the main program TipBit.py in the console window. It will generate the user data files. I would suggest saving those off every once in a while, but that is not within the scope of this project.

The program is currently only tested on Windows systems, though I believe it should work fine on Linux or OSX as well

### Prerequisites

There are two main dependencies:
- [Bitcoin Core](http://www.bitcoin.org) - The Bitcoin Core wallet software, which this bot communicates with using RPC calls
- [Praw](https://praw.readthedocs.io/en/latest/) - The python reddit API library

## Testing the bot

Before you start inviting everyone to use the bot, you'll probably want to test it yourself. Here is the breakdown of how to do that.
- Send a message to the bot's reddit username with 'Register' as the subject line and anything in the body. The bot should respond to you confirming your registration and giving you a deposit address for both legacy and segwit.
- Deposit a small amount (though I suggest something far bigger than the minimum deposit) to that address. The bot should move as much as it can (eating the transaction fee first) to the storage address you specified in PRIMARY_STORAGE_ADDRESS. The bot will send you your balance in a reddit message, confirming the deposit.
- If you have a wallet that you want to sweep clean, you can send a message to the bot's reddit username with 'Sweep Deposit' as the subject line, and with the wallet's private key as the body of the message. The bot will sweep as much as it can from that wallet into the storage address, credit your account, and send your new balance information.
- Send a message to the bot's reddit username with 'Balance' as the subject line and it should respond to you, giving your balance. Please note that if you do this prior to registering, it will tell you to register first.
- Within one of the subreddits you specified in BOT_TEST_SUBS, create a comment in the format '/u/XXX YYY ZZZ', where XXX is replaced with the bot's username, YYY is replaced with the username of the person you're tipping, and ZZZ is replaced with the amount (in mBTC) that you'd like to tip the person. For example:
```
/u/YourBot TipBitDev 123.45
```
- Send a message to the bot with 'Withdraw' in the subject line, and have the body of the message be the address to send it to, then a space, then the amount to withdraw (in mBTC).

## Authors

* **Drew Banyai** - *Initial work* - [DrewBanyai](https://github.com/DrewBanyai)

## Acknowledgments

* Thank you to Ofek Lev, who developed "Bit", the Python Bitcoin library which was utilized in the first version of the bot to do API calls for moving bitcoin and getting information about bitcoin wallets and current bitcoin price and is still used for quickly getting legacy and segwit addresses from private keys. He was also great at answering all of my many annoying questions.
* Huge thanks to the developers of PRAW, the python library for interacting with reddit. Without that, this bot would have never been made.
* And of course, a big thanks to the Bitcoin Core team, even though the RPC call documentation was terrible and there was no python example project available (I'll probably make one at this point).
