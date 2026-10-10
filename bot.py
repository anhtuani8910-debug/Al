import telebot
from telebot import types
import sqlite3
import datetime
import imaplib
import email
import re

# --------------------------------------------------
# CẤU HÌNH HỆ THỐNG THEO YÊU CẦU CỦA BẠN
# --------------------------------------------------
API_TOKEN = '8984782671:AAGPjTtgOG3useX9tCBfvuvgR6gXlDFbWq4'
ADMIN_ID = 8810248698  # ID Admin của bạn
PRICE_PER_DAY = 150    # Giá thuê 1 ngày (VNĐ)
MIN_DEPOSIT = 5000     # Số tiền nạp tối thiểu (VNĐ)
QR_IMAGE_URL = 'https://cdn.phototourl.com/member/2026-10-08-7d18514b-4b87-40ea-9012-3540fccbfeda.jpg'
IMAP_SERVER = 'outlook.office365.com' # Server IMAP (Hỗ trợ Hotmail/Outlook)

bot = telebot.TeleBot(API_TOKEN)

# --------------------------------------------------
# KHỞI TẠO CƠ SỞ DỮ LIỆU (SQLITE)
# --------------------------------------------------
def init_db():
    conn = sqlite3.connect('email_rental_pro.db')
    cursor = conn.cursor()
    
    # Kho email
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            status TEXT DEFAULT 'available'
        )
    ''')
    
    # Số dư người dùng
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0
        )
    ''')
    
    # Lịch sử thuê mail
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rentals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            email_id INTEGER,
            expires_at TEXT
        )
    ''')
    
    # Giao dịch nạp tiền chờ duyệt
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            proof_info TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

def get_or_create_user(user_id):
    conn = sqlite3.connect('email_rental_pro.db')
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, 0))
        conn.commit()
        balance = 0
    else:
        balance = row[0]
    conn.close()
    return balance

# --------------------------------------------------
# HÀM ĐỌC OTP QUA IMAP (BẢO MẬT MẬT KHẨU)
# --------------------------------------------------
def fetch_otp_secure(email_user, email_pass):
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(email_user, email_pass)
        mail.select("inbox")

        status, messages = mail.search(None, 'ALL')
        mail_ids = messages[0].split()
        
        if not mail_ids:
            mail.logout()
            return "📭 Hộp thư hiện tại đang trống, chưa có thư đến."

        latest_id = mail_ids[-1]
        status, data = mail.fetch(latest_id, '(RFC822)')
        
        email_content = ""
        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                subject = msg.get("Subject", "Không có tiêu đề")
                
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            try:
                                email_content = part.get_payload(decode=True).decode(errors='ignore')
                            except:
                                pass
                else:
                    try:
                        email_content = msg.get_payload(decode=True).decode(errors='ignore')
                    except:
                        pass
                
                otp_match = re.search(r'\b\d{4,8}\b', email_content)
                otp_code = otp_match.group(0) if otp_match else "Không tìm thấy mã OTP tự động."

                mail.logout()
                return (
                    f"📩 **Tiêu đề thư:** {subject}\n"
                    f"🔑 **Mã OTP/Code phát hiện:** `{otp_code}`\n\n"
                    f"📝 *Nội dung tóm tắt:* {email_content[:200]}..."
                )

        mail.logout()
        return "⚠️ Đã kết nối nhưng không đọc được nội dung thư."
    except Exception as e:
        return f"❌ Lỗi kết nối IMAP hoặc sai thông tin bảo mật thư viện.\nChi tiết: {str(e)}"

# --------------------------------------------------
# GIAO DIỆN CHÍNH & MENU (KEYBOARD)
# --------------------------------------------------
def main_menu(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📧 Thuê Email", callback_data="menu_rent"),
        types.InlineKeyboardButton("📬 Mail Đang Thuê & Lấy OTP", callback_data="menu_myemail"),
        types.InlineKeyboardButton("💰 Số Dư & Nạp Tiền", callback_data="menu_deposit"),
        types.InlineKeyboardButton("📦 Kho Mail Sẵn Có", callback_data="menu_list")
    )
    if user_id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👑 BẢNG ĐIỀU KHIỂN ADMIN", callback_data="admin_panel"))
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    balance = get_or_create_user(user_id)
    
    welcome_text = (
        f"🤖 **HỆ THỐNG CHO THUÊ EMAIL TỰ ĐỘNG**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 ID của bạn: `{user_id}`\n"
        f"💰 Số dư hiện tại: **{balance} VNĐ**\n"
        f"🏷️ Giá thuê: **{PRICE_PER_DAY} VNĐ / ngày**\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💡 *Hệ thống bảo mật tuyệt đối: Mem chỉ nhận Email và lấy mã OTP tự động, KHÔNG BAO GIỜ lộ mật khẩu!*"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown', reply_markup=main_menu(user_id))

# --------------------------------------------------
# XỬ LÝ CÁC NÚT BẤM (CALLBACK QUERY) CHO USER
# --------------------------------------------------
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    
    if call.data == "menu_rent":
        markup = types.InlineKeyboardMarkup(row_width=3)
        markup.add(
            types.InlineKeyboardButton("1 Ngày (150đ)", callback_data="do_rent_1"),
            types.InlineKeyboardButton("3 Ngày (450đ)", callback_data="do_rent_3"),
            types.InlineKeyboardButton("7 Ngày (1050đ)", callback_data="do_rent_7")
        )
        markup.add(types.InlineKeyboardButton("🔙 Quay lại", callback_data="back_home"))
        bot.edit_message_text("🛒 **Chọn số ngày bạn muốn thuê email:**", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode='Markdown')

    elif call.data.startswith("do_rent_"):
        days = int(call.data.split("_")[2])
        total_cost = PRICE_PER_DAY * days
        balance = get_or_create_user(user_id)

        if balance < total_cost:
            bot.answer_callback_query(call.id, f"❌ Số dư không đủ ({balance}đ)! Vui lòng nạp thêm tiền.", show_alert=True)
            return

        conn = sqlite3.connect('email_rental_pro.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, password FROM emails WHERE status = 'available' LIMIT 1")
        row = cursor.fetchone()

        if not row:
            conn.close()
            bot.answer_callback_query(call.id, "😔 Kho email hiện tại đã hết! Vui lòng quay lại sau.", show_alert=True)
            return

        email_id, email_addr, email_pass = row
        new_balance = balance - total_cost
        
        # Trừ tiền & Đổi trạng thái mail
        cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, user_id))
        cursor.execute("UPDATE emails SET status = 'rented' WHERE id = ?", (email_id,))
        
        expires_at = datetime.datetime.now() + datetime.timedelta(days=days)
        expires_str = expires_at.strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("INSERT INTO rentals (user_id, email_id, expires_at) VALUES (?, ?, ?)", (user_id, email_id, expires_str))
        conn.commit()
        conn.close()

        success_text = (
            f"🎉 **THUÊ EMAIL THÀNH CÔNG!**\n\n"
            f"📧 **Email:** `{email_addr}`\n"
            f"🔒 **Mật khẩu:** *[Đã được bảo mật tuyệt đối]*\n"
            f"⏳ **Thời hạn:** {days} ngày (Hết hạn: {expires_str})\n"
            f"💸 **Đã thanh toán:** {total_cost} VNĐ\n"
            f"💰 **Số dư còn lại:** {new_balance} VNĐ\n\n"
            f"👇 *Bấm nút bên dưới để lấy mã OTP tự động bất cứ lúc nào!*"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📥 Lấy mã OTP ngay", callback_data="get_otp_action"))
        markup.add(types.InlineKeyboardButton("🏠 Về trang chủ", callback_data="back_home"))
        bot.edit_message_text(success_text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode='Markdown')

    elif call.data == "menu_myemail" or call.data == "get_otp_action":
        conn = sqlite3.connect('email_rental_pro.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT e.email, e.password, r.expires_at 
            FROM rentals r 
            JOIN emails e ON r.email_id = e.id 
            WHERE r.user_id = ? 
            ORDER BY r.id DESC LIMIT 1
        ''', (user_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            bot.answer_callback_query(call.id, "⚠️ Bạn chưa thuê email nào!", show_alert=True)
            return

        email_addr, email_pass, expires_str = row
        
        bot.answer_callback_query(call.id, "🔄 Đang kết nối hộp thư để quét OTP...")
        otp_result = fetch_otp_secure(email_addr, email_pass)

        result_text = (
            f"📬 **THÔNG TIN EMAIL ĐANG THUÊ:**\n"
            f"📧 **Email:** `{email_addr}`\n"
            f"🔒 **Mật khẩu:** *[Đã ẩn an toàn]*\n"
            f"⏳ **Hết hạn:** {expires_str}\n\n"
            f"📥 **KẾT QUẢ QUÉT HỘP THƯ (OTP):**\n{otp_result}"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Làm mới / Lấy OTP lại", callback_data="get_otp_action"))
        markup.add(types.InlineKeyboardButton("🏠 Về trang chủ", callback_data="back_home"))
        bot.edit_message_text(result_text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode='Markdown')

    elif call.data == "menu_deposit":
        deposit_text = (
            f"💰 **HƯỚNG DẪN NẠP TIỀN TỰ ĐỘNG**\n\n"
            f"📌 Mức nạp tối thiểu: **{MIN_DEPOSIT:,} VNĐ**\n"
            f"1️⃣ Quét mã QR bên dưới bằng ứng dụng ngân hàng.\n"
            f"2️⃣ Nhập chính xác nội dung chuyển khoản: `NAP {user_id}`\n"
            f"3️⃣ Sau khi chuyển xong, bấm nút xác nhận bên dưới để hệ thống gửi thông báo về máy Admin duyệt.\n\n"
            f"👇 *Nội dung chuyển khoản bắt buộc:* `NAP {user_id}`"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Tôi đã chuyển khoản & Gửi biên lai", callback_data="confirm_deposit"))
        markup.add(types.InlineKeyboardButton("🔙 Quay lại", callback_data="back_home"))
        
        # Gửi ảnh QR kèm hướng dẫn
        bot.send_photo(call.message.chat.id, QR_IMAGE_URL, caption=deposit_text, parse_mode='Markdown', reply_markup=markup)
        bot.delete_message(call.message.chat.id, call.message.message_id)

    elif call.data == "confirm_deposit":
        msg = bot.send_message(call.message.chat.id, "📥 Vui lòng nhập số tiền bạn đã chuyển khoản (Ví dụ: `10000` hoặc gửi ảnh chụp màn hình bill giao dịch):")
        bot.register_next_step_handler(msg, process_user_deposit_amount)

    elif call.data == "menu_list":
        conn = sqlite3.connect('email_rental_pro.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM emails WHERE status = 'available'")
        count = cursor.fetchone()[0]
        conn.close()

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Quay lại", callback_data="back_home"))
        bot.edit_message_text(f"📦 Số lượng email trống sẵn sàng cho thuê: **{count}** mail.\n🏷️ Giá: **{PRICE_PER_DAY} VNĐ/ngày**", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode='Markdown')

    elif call.data == "back_home":
        balance = get_or_create_user(user_id)
        home_text = (
            f"🤖 **HỆ THỐNG CHO THUÊ EMAIL TỰ ĐỘNG**\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 ID: `{user_id}` | 💰 Số dư: **{balance} VNĐ**\n"
            f"🏷️ Giá thuê: **{PRICE_PER_DAY} VNĐ / ngày**\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        bot.edit_message_text(home_text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=main_menu(user_id), parse_mode='Markdown')

    elif call.data == "admin_panel" and user_id == ADMIN_ID:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📋 Xem toàn bộ Kho Mail", callback_data="adm_list_mail"),
            types.InlineKeyboardButton("📥 Thêm 1 Mail (/addmail)", callback_data="adm_guide_add"),
            types.InlineKeyboardButton("🔙 Về trang chủ", callback_data="back_home")
        )
        bot.edit_message_text("👑 **BẢNG QUẢN TRỊ TỐI CAO (ADMIN)**", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode='Markdown')

    elif call.data == "adm_list_mail" and user_id == ADMIN_ID:
        conn = sqlite3.connect('email_rental_pro.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, password, status FROM emails")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            bot.answer_callback_query(call.id, "Kho mail trống!", show_alert=True)
            return

        res = "📋 **KHO MAIL TRONG HỆ THỐNG:**\n\n"
        for r in rows:
            icon = "🟢" if r[3] == 'available' else "🔴"
            res += f"{icon} `ID:{r[0]}` | `{r[1]}` | `{r[2]}` ({r[3]})\n"
        
        if len(res) > 4000:
            res = res[:4000]
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔙 Quay lại Admin", callback_data="admin_panel"))
        bot.edit_message_text(res, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode='Markdown')

    elif call.data == "adm_guide_add" and user_id == ADMIN_ID:
        guide = "💡 Để thêm mail, hãy gửi tin nhắn chat theo cú pháp:\n`/addmail email@domain.com|matkhau`\nHoặc dùng `/addbulk` để thêm nhiều mail cùng lúc."
        bot.answer_callback_query(call.id, guide, show_alert=True)

# --------------------------------------------------
# XỬ LÝ NẠP TIỀN & ĐẨY THÔNG BÁO VỀ CHO ADMIN DUYỆT
# --------------------------------------------------
def process_user_deposit_amount(message):
    user_id = message.from_user.id
    try:
        amount = int(message.text.strip())
        if amount < MIN_DEPOSIT:
            bot.reply_to(message, f"❌ Số tiền nạp tối thiểu là **{MIN_DEPOSIT:,} VNĐ**. Vui lòng thao tác lại!", parse_mode='Markdown')
            return
    except ValueError:
        bot.reply_to(message, "⚠️ Vui lòng chỉ nhập số tiền hợp lệ (Ví dụ: `10000`). Thao tác đã hủy.")
        return

    # Lưu vào DB chờ duyệt
    conn = sqlite3.connect('email_rental_pro.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO deposits (user_id, amount) VALUES (?, ?)", (user_id, amount))
    deposit_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Đẩy thông báo tức thì về máy Admin
    admin_notify_text = (
        f"🔔 **CÓ YÊU CẦU NẠP TIỀN MỚI CẦN DUYỆT!**\n\n"
        f"👤 **User ID:** `{user_id}`\n"
        f"💰 **Số tiền yêu cầu:** `{amount:,} VNĐ`\n"
        f"📝 **Nội dung CK:** `NAP {user_id}`\n\n"
        f"*(Chỉ bạn mới có quyền quyết định duyệt hoặc từ chối)*"
    )
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Duyệt (+ Tiền)", callback_data=f"approve_{deposit_id}_{user_id}_{amount}"),
        types.InlineKeyboardButton("❌ Từ chối", callback_data=f"reject_{deposit_id}_{user_id}_{amount}")
    )
    
    try:
        bot.send_message(ADMIN_ID, admin_notify_text, parse_mode='Markdown', reply_markup=markup)
        bot.reply_to(message, "✅ Đã gửi yêu cầu nạp tiền của bạn về cho Admin. Vui lòng chờ Admin xác nhận và cộng tiền vào tài khoản!", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"⚠️ Gửi yêu cầu thành công nhưng lỗi thông báo Admin: {str(e)}")

# Admin bấm nút Duyệt hoặc Từ chối nạp tiền
@bot.callback_query_handler(func=lambda call: call.data.startswith(('approve_', 'reject_')))
def handle_admin_approval(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "⛔ Bạn không có quyền quyết định!", show_alert=True)
        return

    parts = call.data.split('_')
    action = parts[0]
    deposit_id = parts[1]
    target_user_id = int(parts[2])
    amount = int(parts[3])

    conn = sqlite3.connect('email_rental_pro.db')
    cursor = conn.cursor()

    if action == 'approve':
        # Cộng tiền cho mem
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, target_user_id))
        conn.commit()
        conn.close()

        bot.answer_callback_query(call.id, f"✅ Đã duyệt cộng {amount:,} VNĐ cho user {target_user_id}!")
        bot.edit_message_text(f"✅ **ĐÃ DUYỆT THÀNH CÔNG**\n- Đã cộng **{amount:,} VNĐ** cho User `{target_user_id}`.", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='Markdown')
        
        # Báo cho mem biết đã được duyệt
        try:
            bot.send_message(target_user_id, f"🎉 **NẠP TIỀN THÀNH CÔNG!**\nAdmin đã duyệt và cộng **{amount:,} VNĐ** vào tài khoản của bạn.", parse_mode='Markdown')
        except:
            pass

    elif action == 'reject':
        conn.close()
        bot.answer_callback_query(call.id, f"❌ Đã từ chối giao dịch của user {target_user_id}!")
        bot.edit_message_text(f"❌ **ĐÃ TỪ CHỐI GIAO DỊCH**\n- Yêu cầu nạp {amount:,} VNĐ của User `{target_user_id}` đã bị từ chối.", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode='Markdown')
        
        # Báo cho mem biết bị từ chối
        try:
            bot.send_message(target_user_id, f"❌ **NẠP TIỀN THẤT BẠI**\nYêu cầu nạp **{amount:,} VNĐ** của bạn đã bị Admin từ chối (có thể do sai nội dung hoặc chưa nhận được tiền).", parse_mode='Markdown')
        except:
            pass

# --------------------------------------------------
# LỆNH DÀNH RIÊNG CHO ADMIN QUẢN LÝ KHO MAIL
# --------------------------------------------------
@bot.message_handler(commands=['addmail'])
def add_email(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Bạn không có quyền!")
        return

    try:
        raw_text = message.text.split(maxsplit=1)[1]
        email, password = raw_text.strip().split('|')
        
        conn = sqlite3.connect('email_rental_pro.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO emails (email, password) VALUES (?, ?)", (email.strip(), password.strip()))
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✅ [Admin] Đã thêm email:\n📧 `{email.strip()}`", parse_mode='Markdown')
    except sqlite3.IntegrityError:
        bot.reply_to(message, "⚠️ Email này đã tồn tại trong hệ thống!")
    except Exception:
        bot.reply_to(message, "⚠️ Sai cú pháp! Dùng: `/addmail email|matkhau`", parse_mode='Markdown')

@bot.message_handler(commands=['addbulk'])
def add_bulk(message):
    if message.from_user.id != ADMIN_ID:
        return
    msg = bot.reply_to(message, "📥 Gửi danh sách định dạng `email|password` (mỗi dòng 1 mail):\n*(Gửi `/cancel` để hủy)*", parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_bulk_data)

def process_bulk_data(message):
    if message.text == '/cancel':
        bot.reply_to(message, "🚫 Đã hủy.")
        return

    lines = message.text.strip().split('\n')
    success = 0
    fail = 0

    conn = sqlite3.connect('email_rental_pro.db')
    cursor = conn.cursor()
    for line in lines:
        if '|' in line:
            parts = line.split('|')
            if len(parts) >= 2:
                try:
                    cursor.execute("INSERT INTO emails (email, password) VALUES (?, ?)", (parts[0].strip(), parts[1].strip()))
                    success += 1
                except:
                    fail += 1
    conn.commit()
    conn.close()
    bot.reply_to(message, f"📊 [Admin] Thêm thành công: {success} | Lỗi/Trùng: {fail}", parse_mode='Markdown')

# --------------------------------------------------
# CHẠY BOT
# --------------------------------------------------
if __name__ == '__main__':
    # Tạo bảng deposits nếu chưa có từ bản trước
    try:
        conn = sqlite3.connect('email_rental_pro.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deposits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER
            )
        ''')
        conn.commit()
        conn.close()
    except:
        pass

    print("🤖 Bot Telegram Cho Thuê Email Pro đang chạy hoàn hảo...")
    bot.infinity_polling()
