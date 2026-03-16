"""
bot.py — Telegram Bot integration for receiving voice messages and triggering playback.
"""
import os
import time
import logging
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

import audio
from config import load_config, save_config

logger = logging.getLogger("telegram_bot")

_bot_thread = None
_bot_instance = None
_bot_stop_event = threading.Event()

# Temporary store for pending voice messages: {chat_id: {file_id: ..., message_id: ...}}
_pending_voices = {}

def start_bot():
    """Starts the Telegram bot in a background thread if token is present."""
    global _bot_thread, _bot_instance, _bot_stop_event
    
    cfg = load_config()
    token = cfg.get("TELEGRAM_BOT_TOKEN", "").strip()
    
    if not token:
        logger.info("No Telegram Bot Token configured. Bot is disabled.")
        return

    if _bot_thread and _bot_thread.is_alive():
        logger.info("Bot is already running.")
        return

    _bot_stop_event.clear()
    _bot_instance = telebot.TeleBot(token)
    _register_handlers(_bot_instance)

    _bot_thread = threading.Thread(target=_bot_polling, args=(_bot_instance,), daemon=True)
    _bot_thread.start()
    logger.info("Telegram Bot started.")


def stop_bot():
    """Stops the telegram bot polling."""
    global _bot_instance, _bot_stop_event
    if _bot_instance:
        logger.info("Stopping Telegram Bot...")
        _bot_stop_event.set()
        _bot_instance.stop_polling()
        _bot_instance = None

def restart_bot():
    stop_bot()
    time.sleep(1) # give it time to fully stop
    start_bot()

def is_authorized(user_id):
    cfg = load_config()
    auth_users = cfg.get("TELEGRAM_AUTHORIZED_USERS", [])
    return user_id in auth_users

def add_authorized_user(user_id):
    cfg = load_config()
    auth_users = cfg.get("TELEGRAM_AUTHORIZED_USERS", [])
    if user_id not in auth_users:
        auth_users.append(user_id)
        save_config({"TELEGRAM_AUTHORIZED_USERS": auth_users})

def _register_handlers(bot: telebot.TeleBot):
    
    @bot.message_handler(commands=['start'])
    def handle_start(message):
        if is_authorized(message.from_user.id):
            bot.reply_to(message, "Вы уже авторизованы. Можете отправлять голосовые сообщения для трансляции.")
        else:
            bot.reply_to(message, "Привет! Для доступа к трансляции голосовых сообщений, введите пароль (команда: `/auth <пароль>`)", parse_mode="Markdown")

    @bot.message_handler(commands=['auth'])
    def handle_auth(message):
        if is_authorized(message.from_user.id):
            bot.reply_to(message, "Вы уже авторизованы!")
            return
            
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "Использование: `/auth пароль`", parse_mode="Markdown")
            return
            
        cfg = load_config()
        password = parts[1].strip()
        expected = cfg.get("TELEGRAM_BOT_PASSWORD", "ring")
        
        if password == expected:
            add_authorized_user(message.from_user.id)
            bot.reply_to(message, "✅ Пароль верный! Вы успешно авторизованы.\nТеперь вы можете отправлять мне голосовые сообщения, и я буду транслировать их через систему оповещения.")
            logger.info(f"Telegram user {message.from_user.id} authorized successfully.")
        else:
            bot.reply_to(message, "❌ Неверный пароль.")
            logger.warning(f"Failed authorization attempt by Telegram user {message.from_user.id}")

    @bot.message_handler(content_types=['voice'])
    def handle_voice(message):
        if not is_authorized(message.from_user.id):
            bot.reply_to(message, "У вас нет доступа. Сначала введите пароль через `/auth`.", parse_mode="Markdown")
            return
            
        file_id = message.voice.file_id
        chat_id = message.chat.id
        
        # Store pending
        if chat_id not in _pending_voices:
            _pending_voices[chat_id] = {}
            
        _pending_voices[chat_id] = file_id
        
        markup = InlineKeyboardMarkup()
        btn_yes = InlineKeyboardButton("✅ Воспроизвести", callback_data=f"play_voice")
        btn_no = InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_voice")
        markup.add(btn_yes, btn_no)
        
        bot.reply_to(message, "Воспроизвести это голосовое сообщение по громкой связи?", reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data in ["play_voice", "cancel_voice"])
    def handle_voice_callback(call):
        chat_id = call.message.chat.id
        
        if call.data == "cancel_voice":
            _pending_voices.pop(chat_id, None)
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="Отменено. Голосовое сообщение удалено.")
            return
            
        if call.data == "play_voice":
            file_id = _pending_voices.pop(chat_id, None)
            if not file_id:
                bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="Ошибка: Файл не найден в очереди. Попробуйте отправить заново.")
                return
                
            bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="⏳ Загрузка и конвертация аудио...")
            
            try:
                # 1. Download from Telegram
                file_info = bot.get_file(file_id)
                downloaded_file = bot.download_file(file_info.file_path)
                
                # Use a dedicated folder for voice messages instead of the main uploads folder
                voice_dir = "voice_messages"
                os.makedirs(voice_dir, exist_ok=True)
                
                # Telegram usually sends OGG Opus
                ogg_path = os.path.join(voice_dir, f"tg_voice_{chat_id}.ogg")
                with open(ogg_path, 'wb') as new_file:
                    new_file.write(downloaded_file)
                
                # 2. Try to convert or play directly
                # Often PyGame has trouble with Opus inside OGG. Let's try converting using Pydub/ffmpeg if installed.
                try:
                    import subprocess
                    import imageio_ffmpeg
                    
                    wav_path = os.path.join(voice_dir, f"tg_voice_{chat_id}.wav")
                    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                    
                    # Run ffmpeg to convert ogg to wav directly, bypassing pydub/ffprobe requirements
                    subprocess.run(
                        [ffmpeg_exe, "-y", "-i", ogg_path, wav_path],
                        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                    
                    audio_path_to_play = wav_path
                    logger.info("Successfully converted Telegram voice to WAV using direct ffmpeg call.")
                except Exception as e:
                    logger.warning(f"Could not convert with pydub (FFmpeg missing?): {e}. Will attempt to play native OGG.")
                
                # 3. Play the audio using existing audio module
                bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="🔊 Воспроизведение...")
                audio.ring_bell(sound_file=audio_path_to_play, duration=0) # duration 0 or None means play full
                
                bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text="✅ Воспроизведение успешно завершено.")
                
            except Exception as e:
                logger.error(f"Error handling Telegram voice: {e}")
                bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, text=f"❌ Ошибка вывода звука: {e}")

def _bot_polling(bot_instance):
    while not _bot_stop_event.is_set():
        try:
            bot_instance.polling(none_stop=True, timeout=10, long_polling_timeout=10)
        except Exception as e:
            if not _bot_stop_event.is_set():
                logger.error(f"Telegram bot polling exception: {e}")
                time.sleep(5)
