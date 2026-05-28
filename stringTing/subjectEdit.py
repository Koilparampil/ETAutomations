import pandas as pd

def subjectDecision(inv_num, eta: pd.Timestamp, notif, didPay: bool)-> str:
    if notif:
        if eta <= pd.Timestamp.now() and didPay:
            return f"Invoice for Booking no. {inv_num}. ****ARRIVED ON {eta.strftime('%m/%d')}. PLEASE CLEAR THE CARGO****"
        elif eta <= pd.Timestamp.now() and not didPay:
            return f"Invoice for Booking no. {inv_num}. ****ARRIVED ON {eta.strftime('%m/%d')}. PLEASE PAY AND CLEAR THIS PAST DUE INVOICE AND CLEAR THE CARGO****"
        elif eta >= pd.Timestamp.now() and didPay:
            return f"Invoice for Booking no. {inv_num}. ***ESTIMATED ARRIVING ON {eta.strftime('%m/%d')}.****"
        elif eta >= pd.Timestamp.now() and not didPay:
            return f"Invoice for Booking no. {inv_num}. ***ESTIMATED ARRIVING ON {eta.strftime('%m/%d')}. PLEASE MAKE PAYMENT ARRANGEMENT****"
        else:
            return f"Invoice for Booking no. {inv_num}. ***Please Check Attached Invoice for ETA***"
    else:
        if eta <= pd.Timestamp.now() and didPay:
            return f"Invoice for Booking no. {inv_num}. ****ARRIVED ON {eta.strftime('%m/%d')}. PLEASE CLEAR THE CARGO****"
        elif eta <= pd.Timestamp.now() and not didPay:
            return f"Invoice for Booking no. {inv_num}. ****ARRIVED ON {eta.strftime('%m/%d')}. PLEASE PLEASE PAY AND CLEAR THE CARGO****"
        elif eta >= pd.Timestamp.now() and didPay:
            return f"Invoice for Booking no. {inv_num}. ***ESTIMATED ARRIVING ON {eta.strftime('%m/%d')}.****"
        elif eta >= pd.Timestamp.now() and not didPay:
            return f"Invoice for Booking no. {inv_num}. ***ESTIMATED ARRIVING ON {eta.strftime('%m/%d')}. PLEASE MAKE PAYMENT ARRANGEMENT****"
        else:
            return f"Invoice for Booking no. {inv_num}. ***Please Check Attached Invoice for ETA***"    