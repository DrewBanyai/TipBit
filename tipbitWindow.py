from tkinter import *
import tipbitUtilities

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
tipStorageDiffStringVar = StringVar()
eventListbox = Listbox(window)
eventListbox.place(x=0, y=22, anchor='nw', width=800, height=556)
eventListboxQueue = []
bitcoinValueStringVar = StringVar()
tipBalanceValueStringVar = StringVar()

def SetupGUI():
	Label(window, textvariable=tipBalanceStringVar, anchor='center', justify=CENTER, font='Arial 9 bold').place(x=5, y=10, anchor='w')
	Label(window, textvariable=tipStorageDiffStringVar, anchor='center', justify=CENTER, font='Arial 9 bold').place(x=795, y=10, anchor='e')
	#canvas.create_line(400, 0, 400, 20)
	Label(window, textvariable=bitcoinValueStringVar, anchor='center', justify=CENTER, font='Arial 9 bold').place(x=5, y=590, anchor='w')
	Label(window, textvariable=tipBalanceValueStringVar, anchor='center', justify=CENTER, font='Arial 9 bold').place(x=795, y=590, anchor='e')
	
def UpdateWindow():
	ProcessEventQueue()
	window.update_idletasks()
	window.update()
	
def ProcessEventQueue():
	for item in eventListboxQueue: AddEventString(item);
	eventListboxQueue.clear()
	
def AddEventString(eventString, showInConsole=True, outsideMainThread=False):
	if outsideMainThread:
		eventListboxQueue.append(eventString)
		return
		
	if showInConsole:
		global eventListbox
		eventListbox.insert(END, eventString)
	tipbitUtilities.ConsolePrint(eventString)
	
def SetGUITipBalanceString(tipBalance):
	tipBalanceStringVar.set('TIP BALANCE: {:,} satoshis'.format(tipBalance))
	
def SetGUISolvencyDiffString(solvencyDiff):
	tipStorageDiffStringVar.set(('SOLVENT') if (solvencyDiff == 0) else ('SOLVENCY DIFF: {:,}'.format(solvencyDiff)))
	
def SetGUIBitcoinValueString(bitcoinValue):
	bitcoinValueStringVar.set('BITCOIN VALUE: ${:,.2f}'.format(bitcoinValue))
	
def SetGUITipBalanceValueString(tipBalanceValue):
	tipBalanceValueStringVar.set('TIP BALANCE VALUE: ${:,.2f}'.format(tipBalanceValue))