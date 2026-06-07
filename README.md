# 💙 Do'stlik & Tanishuv Telegram Bot

## Fayl tuzilmasi
```
dating_bot/
├── bot.py              # Backend (aiogram 3)
├── database.py         # PostgreSQL funksiyalar
├── config.py           # Sozlamalar (TOKEN, URL)
├── requirements.txt    # Python paketlar
├── webapp/
│   ├── index.html      # Asosiy sahifa
│   ├── style.css       # Oq-ko'k dizayn
│   └── app.js          # Frontend logika
└── README.md
```

---

## 🚀 O'rnatish va ishga tushirish

### 1. Bot yaratish
1. [@BotFather](https://t.me/BotFather) ga boring
2. `/newbot` buyrug'ini yuboring
3. Bot nomini va username ni bering
4. **TOKEN** ni oling

### 2. WebApp hostingga joylashtirish
`webapp/` papkasini hosting ga yuklang:
- **GitHub Pages** (bepul):  
  1. GitHub repo yarating
  2. `webapp/` papkasini push qiling  
  3. Settings → Pages → Deploy from branch  
  4. URL: `https://USERNAME.github.io/REPO_NAME`
- Yoki **Netlify**, **Vercel** bilan ham bo'ladi

### 3. config.py ni sozlash
```python
BOT_TOKEN = "123456:ABC-DEF..."        # BotFather dan
DATABASE_URL = "postgresql://..."       # Railway PostgreSQL
WEBAPP_URL = "https://USERNAME.github.io/REPO_NAME"  # Hosting URL
```

### 4. app.js ni sozlash
`app.js` faylida bot username ni o'zgartiring:
```javascript
const botUsername = 'YOUR_BOT_USERNAME';  // @ belgisisiz
```

### 5. BotFather da WebApp sozlash
```
/setmenubutton → botingizni tanlag → URL kiriting → nom kiriting
```

### 6. Python paketlarni o'rnatish
```bash
pip install -r requirements.txt
```

### 7. Ishga tushirish
```bash
python bot.py
```

---

## ⚙️ Funksiyalar

| Funksiya | Holat |
|---|---|
| ✅ Anketa to'ldirish | Tayyor |
| ✅ Jins tanlash | Tayyor |
| ✅ Shahar suggest | Tayyor |
| ✅ Qiziqishlar chips | Tayyor |
| ✅ Maqsad chips | Tayyor |
| ✅ Foto yuklash | Tayyor |
| ✅ Qidirish + filtrlar | Tayyor |
| ✅ Like yuborish | Tayyor |
| ✅ Match tizimi | Tayyor |
| ✅ Blok qilish | Tayyor |
| ✅ Do'st taklif qilish | Tayyor |
| ✅ Referral tizimi | Tayyor |
| ✅ Bepul yozish (2 do'st) | Tayyor |
| ✅ PostgreSQL baza | Tayyor |

---

## 🗄️ Database jadvallar
- `users` — foydalanuvchilar
- `likes` — like lar
- `matches` — o'zaro like (match)
- `blocks` — bloklangan
- `invites` — taklif qilinganlar

---

## 📞 Yordam
Muammolar bo'lsa, botni qayta ishga tushiring:
```bash
python bot.py
```
