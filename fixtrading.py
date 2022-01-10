import quickfix44
import quickfix
import numpy as np
import string
ALPHABET = np.array(list(string.ascii_lowercase + ' '))
ALPHABET = [x for x in ALPHABET if x!=" "]



def create_order(symbol, side, price, lots, board = "TQBR"):
    '''
    creates order, if price = None creates market order
    buy is a bool variable
    returns message
    example: create_order("AMZN-RM", "sell", 224044, 1, board = "FQBR" )
    '''
    msg = quickfix44.NewOrderSingle()
    random_cl_ord_id = "".join(np.random.choice(ALPHABET, size=20))
    msg.setField(quickfix.ClOrdID(random_cl_ord_id)) #unique, apparently can be used to identify the order
    
    if price is None:
        msg.setField(quickfix.OrdType(quickfix.OrdType_MARKET))
    else:
        msg.setField(quickfix.OrdType(quickfix.OrdType_LIMIT))
        msg.setField(quickfix.Price(price))
        

    group = quickfix.Group(386, 336) #NoTradingSession would be filled automatically
    group.setField(quickfix.TradingSessionID(board)) #TQBR for RUS, FQBR for foreign
    msg.addGroup(group)


    msg.setField(quickfix.Symbol(symbol)) #seccode
    msg.setField(quickfix.Account("L00-000012D8")) #торговый счет
    
    if side == "buy":
        msg.setField(quickfix.Side(quickfix.Side_BUY)) #side
    elif side == "sell":
        msg.setField(quickfix.Side(quickfix.Side_SELL)) #side
    else:
        raise ValueError("invalid side")
        

    msg.setField(quickfix.OrderQty(lots)) #В ЛОТАХ!!

    #CLIENT CODE
    group = quickfix.Group(453, 452) 
    group.setField(quickfix.PartyID("2076087002")) #client code, can find in terminal
    group.setField(quickfix.PartyIDSource(quickfix.PartyIDSource_PROPRIETARY))
    group.setField(quickfix.PartyRole(quickfix.PartyRole_CLIENT_ID))
    msg.addGroup(group)

    return msg
