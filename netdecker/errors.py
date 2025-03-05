class Error(Exception):
    """Base class for exceptions in this module."""
    pass

class CardListInputError(Error):
    """
    Exception raised for errors in the LoanList Modal TextInput.

    Attributes:
        expression -- input expression in which the error occurred
        message -- explanation of the error
    """

    def __init__(self, line_errors):
        self.line_errors = line_errors

    def __str__(self):
        message = f"error parsing provided CardList\n\n Please ensure all lines follow the format of `<integer> <cardname>`.\n\n The following lines raised errors:\n```"
        for line in "\n".join(self.line_errors):
            message += line
        message += "```"
        return message
    
class CardNotFoundError(Error):
    """
    Exception raised when unable to find cards in database to return.
    """
    def __init__(self, card_errors):
        self.card_errors = card_errors
    def __str__(self):
        message = f"error finding card(s) in database.\n\n Please ensure all cards and quantities have matching loans.\n\n The following lines raised errors:\n\n```"
        for card_name, quantity in self.card_errors:
            message += f"{quantity} {card_name}\n"
        message += "```"
        return message
    
class CardInsufficientAvailable(Error):
    def __init__(self, requested, available):
        self.name = name
        self.requested = requested,
        self.available = available

    def __str__(self):
        return f"Requested {self.quantity} cards when {self.available} available"
    

class CardInsufficientQuantity(Error):
    def __init__(self, name, requested, quantity):
        self.name = name
        self.requested = requested,
        self.quantity = quantity 

    def __str__(self):
        return f"insufficient quantity to perform action, requested {self.requested} cards when {self.quantity} available"
    
class DomainNotSupported(Error):
    def __init__():
        pass

class UnableToFetchDecklist(Error):
    def __init__():
        pass