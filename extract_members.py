#!/usr/bin/env python3
"""
سكريبت لاستخراج أعضاء مجموعة تليجرام
"""
import asyncio
from app.clients.sessions_manager import SessionsManager
from app.clients.telegram_client import TelegramClientManager
from app.database import db
from app.modules.extractor import ExtractorService
from app.config import settings

async def extract_group_members():
    print("🔄 جاري الاتصال بتليجرام...")
    
    # Initialize
    await db.init_models()
    sessions = SessionsManager(db)
    await sessions.sync_from_disk()
    
    tg_manager = TelegramClientManager(db)
    active_session = await sessions.get_active_session() or "default"
    await tg_manager.start_session(active_session, sessions.session_file(active_session))
    
    extractor = ExtractorService(tg_manager, db, settings.default_delay)
    
    # Ask for group
    print("\n📝 أدخل معرف المجموعة أو رابطها:")
    print("   أمثلة: @mygroup أو https://t.me/mygroup أو -100123456789")
    group = input("المجموعة: ").strip()
    
    if not group:
        print("❌ لم تدخل معرف المجموعة!")
        return
    
    print(f"\n🔍 جاري استخراج أعضاء: {group}")
    print("⏳ قد يستغرق هذا بعض الوقت...\n")
    
    try:
        members = await tg_manager.iter_group_members(group)
        print(f"\n✅ تم استخراج {len(members)} عضو!")
        
        # Save to database
        saved_count = 0
        for member in members:
            if member.get('username'):
                await db.upsert_user(
                    user_id=member['user_id'],
                    username=member['username'],
                    phone=member.get('phone'),
                    last_seen=member.get('last_seen'),
                    country_code=None
                )
                saved_count += 1
        
        print(f"💾 تم حفظ {saved_count} مستخدم في قاعدة البيانات")
        print(f"\n🎉 الآن يمكنك إرسال رسائل جماعية لهم!")
        
    except Exception as e:
        print(f"\n❌ خطأ: {e}")
    finally:
        await tg_manager.stop_all()
        await db.close()

if __name__ == "__main__":
    asyncio.run(extract_group_members())
