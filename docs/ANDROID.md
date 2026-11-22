# Sweetie Fox для Android — что уже готово и что делать дальше

## Уже сделано в этом архиве
- **Сервер** (`server/license_server.py`): поле `"platform": "pc" | "android"` во всех запросах
  (`register`, `login`, `extend`, `check`). Не указано = `pc`, старые клиенты работают как раньше.
  У ПК и телефона **отдельные привязки** (`hwid` и `hwid_android`): один аккаунт можно использовать
  на одном ПК и на одном телефоне. База мигрирует сама при запуске.
- **Админка**: колонка «Телефон»; «Сбросить привязку» сбрасывает обе
  (API: `/api/admin/reset_hwid` с `"platform": "pc"|"android"` — только одну).
- **Мод**: кнопка «Sweetie Menu» в углу экрана паузы (Esc) — меню открывается касанием, без Right Shift.
  (`PulseTouch.java`; не компилировалось в этой среде — собери мод через CI/Gradle и проверь.)

## Запросы для Android-приложения (JSON, POST)
Адрес — тот же сервер лицензий.

| Метод | Тело |
|---|---|
| `/api/register` | `username, password, key, hwid, platform:"android"` |
| `/api/login`    | `username, password, hwid, platform:"android"` |
| `/api/extend`   | `username, password, key, hwid, platform:"android"` |
| `/api/check`    | `token, hwid, platform:"android"` |

Ответ при успехе: `{ok:true, username, expires, server_time, token}`.
Ошибка: `{ok:false, error, code}`. Коды: `bad_creds, bad_key, key_used, exists, expired, hwid,
session, rate, bad_request, banned`. При `banned` показывать экран блокировки с кнопкой на
https://t.me/sweetielauncher. `expires = 0` — навсегда.

`hwid` на Android: хэш от `Settings.Secure.ANDROID_ID` + имя приложения (32 hex-символа).

## Шаги дальше (делаешь ты)
1. Android Studio + Git + JDK 17 + Android SDK/NDK.
2. Выбери актуальный форк Pojav-лаунчера (PojavLauncher / Zalith), проверь лицензию (GPL → исходники открывать).
3. Собери оригинал, поставь на телефон, запусти Minecraft 1.21.11. Если не идёт — дальше не двигаться.
4. Проверь, какие моды запускаются (pulselite, Sodium и т.п.).
5. Пришли ссылку на форк и список рабочих модов — переписываем экраны входа/регистрации/блокировки,
   автоустановку модов и стиль под наш дизайн.
