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
storageBalanceStringVar = StringVar()
tipStorageDiffStringVar = StringVar()
tipBalanceStringVar.set("tip_balance")
storageBalanceStringVar.set("storage_balance")
tipStorageDiffStringVar.set("tip_storage_difference")
eventListbox = Listbox(window)
eventListbox.place(x=0, y=40, anchor='nw', width=800, height=360)
eventListboxQueue = []
depositsListbox = Listbox(window)
depositsListbox.place(x=5, y=440, anchor='nw', width=390, height=155)
storageListbox = Listbox(window)
storageListbox.place(x=405, y=440, anchor='nw', width=390, height=155)

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
	Label(window, text='DEPOSIT TRANSACTIONS', anchor='center', justify=CENTER, font='Arial 9 bold').place(x=200, y=430, anchor='center')
	Label(window, text='STORAGE TRANSACTIONS', anchor='center', justify=CENTER, font='Arial 9 bold').place(x=600, y=430, anchor='center')
	
def UpdateWindow():
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
	tipBalanceStringVar.set(tipBalance)
	
def SetGUIStorageBalanceString(storageBalance):
	storageBalanceStringVar.set(storageBalance)
	
def SetGUISolvencyDiffString(solvencyDiff):
	tipStorageDiffStringVar.set(solvencyDiff)
	
def ApplyPendingDepositsToList(pendingDepositList):
	depositsListbox.delete(0, END)
	for item in pendingDepositList: depositsListbox.insert(END, item)
	pendingDepositList.clear()
	
def ApplyPendingStorageToList(pendingStorageList):
	storageListbox.delete(0, END)
	for item in pendingStorageList: storageListbox.insert(END, item)
	pendingStorageList.clear()