from telebot import types

def create_main_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('Add User', 'Show User')
    markup.row('Delete User', 'Server Info')
    markup.row('Backup Server')

    

def create_user_markup():
    """
    Create a reply keyboard for normal users.

    Buttons:
    - Subscribe: start a subscription process
    - My Link: show current subscription link
    - Revoke Link: revoke and regenerate link
    """
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # Row for subscription option
    markup.row('Subscribe')
    # Row for retrieving or revoking user link
    markup.row('My Link', 'Revoke Link')
    return markup

    return markup

