from .command import bot, run_cli_command, ADMIN_USER_IDS
try:
    from .command import CLIT_PATH
except ImportError:
    CLIT_PATH = 'core/cli.py'
from .common import create_user_markup
import telebot
import os
import json

# Path to mapping file storing Telegram user ID to Hysteria username
USER_MAPPING_FILE = os.path.join(os.path.dirname(__file__), 'tg_users.json')


def load_user_mapping():
    try:
        with open(USER_MAPPING_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def save_user_mapping(mapping):
    with open(USER_MAPPING_FILE, 'w') as f:
        json.dump(mapping, f)


user_mapping = load_user_mapping()
pending_subscriptions = {}


@bot.message_handler(func=lambda message: message.text == 'Subscribe')
def subscribe(message):
    user_id = message.from_user.id
    # If user already has a subscription, inform them
    if str(user_id) in user_mapping:
        bot.send_message(user_id, 'You already have an active subscription.', reply_markup=create_user_markup())
        return
    # Ask for subscription duration
    markup = telebot.types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    markup.add('1 month', '3 months', '6 months', '12 months', 'Cancel')
    msg = bot.send_message(user_id, 'Please choose subscription duration:', reply_markup=markup)
    bot.register_next_step_handler(msg, process_subscription_duration)


def process_subscription_duration(message):
    user_id = message.from_user.id
    text = message.text.strip().lower()
    if text == 'cancel':
        bot.send_message(user_id, 'Subscription cancelled.', reply_markup=create_user_markup())
        return
    months_map = {
        '1 month': 1,
        '3 months': 3,
        '6 months': 6,
        '12 months': 12
    }
    if message.text not in months_map:
        bot.send_message(user_id, 'Invalid selection. Please press Subscribe again and choose a valid option.', reply_markup=create_user_markup())
        return
    months = months_map[message.text]
    pending_subscriptions[user_id] = {'months': months}
    # Request payment screenshot
    bot.send_message(user_id, 'Please send your payment screenshot as a photo.', reply_markup=telebot.types.ReplyKeyboardRemove())


@bot.message_handler(content_types=['photo'])
def handle_payment_photo(message):
    user_id = message.from_user.id
    if user_id not in pending_subscriptions:
        # Ignore photos not related to subscription flow
        return
    data = pending_subscriptions[user_id]
    # Use highest resolution photo
    photo = message.photo[-1]
    file_id = photo.file_id
    data['file_id'] = file_id
    months = data['months']
    # Create inline buttons for admin approval
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(
        telebot.types.InlineKeyboardButton('Approve', callback_data=f'approve_{user_id}'),
        telebot.types.InlineKeyboardButton('Reject', callback_data=f'reject_{user_id}')
    )
    # Send photo with caption to each admin
    caption = f'New subscription request from user {user_id} for {months} month(s). Approve?'
    for admin_id in ADMIN_USER_IDS:
        try:
            bot.send_photo(admin_id, file_id, caption=caption, reply_markup=keyboard)
        except Exception:
            pass
    bot.send_message(user_id, 'Your payment has been sent for review. Please wait for admin approval.')


@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_') or call.data.startswith('reject_'))
def handle_admin_decision(call):
    data_parts = call.data.split('_')
    action = data_parts[0]
    try:
        user_id = int(data_parts[1])
    except (IndexError, ValueError):
        bot.answer_callback_query(call.id, 'Invalid callback data.')
        return
    # Ensure the callback is coming from an admin
    if call.from_user.id not in ADMIN_USER_IDS:
        bot.answer_callback_query(call.id, 'You are not authorized to perform this action.')
        return
    if user_id not in pending_subscriptions:
        bot.answer_callback_query(call.id, 'Request not found or already processed.')
        return
    sub_info = pending_subscriptions.pop(user_id)
    if action == 'approve':
        months = sub_info['months']
        username = f'tg{user_id}'
        expiration_days = months * 30
        # Create user via CLI
        try:
            cmd_add = f'python3 {CLIT_PATH} add-user --username {username} --traffic-limit 300 --expiration-days {expiration_days}'
            run_cli_command(cmd_add)
            # Generate user URI
            cmd_show = f'python3 {CLIT_PATH} show-user-uri --username {username}'
            uri_result = run_cli_command(cmd_show)
            # Save mapping
            user_mapping[str(user_id)] = {'username': username}
            save_user_mapping(user_mapping)
            # Send link to user
            bot.send_message(user_id, f'Your subscription is active!\nYour link:\n{uri_result}', reply_markup=create_user_markup())
            bot.send_message(call.from_user.id, 'User created successfully and link sent.')
        except Exception as e:
            bot.send_message(call.from_user.id, f'Failed to create user: {e}')
    else:
        # Reject request
        bot.send_message(user_id, 'Your subscription request was rejected.', reply_markup=create_user_markup())
        bot.send_message(call.from_user.id, 'Subscription request rejected.')
    bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda message: message.text == 'My Link')
def handle_my_link(message):
    user_id = message.from_user.id
    data = user_mapping.get(str(user_id))
    if not data:
        bot.send_message(user_id, 'You do not have an active subscription.', reply_markup=create_user_markup())
        return
    username = data.get('username')
    try:
        cmd_show = f'python3 {CLIT_PATH} show-user-uri --username {username}'
        uri_result = run_cli_command(cmd_show)
        bot.send_message(user_id, f'Your current link:\n{uri_result}', reply_markup=create_user_markup())
    except Exception as e:
        bot.send_message(user_id, f'Failed to fetch link: {e}')


@bot.message_handler(func=lambda message: message.text == 'Revoke Link')
def handle_revoke_link(message):
    user_id = message.from_user.id
    data = user_mapping.get(str(user_id))
    if not data:
        bot.send_message(user_id, 'You do not have an active subscription.', reply_markup=create_user_markup())
        return
    username = data.get('username')
    try:
        cmd_edit = f'python3 {CLIT_PATH} edit-user --username {username} --renew-password'
        run_cli_command(cmd_edit)
        cmd_show = f'python3 {CLIT_PATH} show-user-uri --username {username}'
        uri_result = run_cli_command(cmd_show)
        bot.send_message(user_id, f'Your link has been renewed:\n{uri_result}', reply_markup=create_user_markup())
    except Exception as e:
        bot.send_message(user_id, f'Failed to renew link: {e}')
