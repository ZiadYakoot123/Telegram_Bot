#!/usr/bin/env python3
"""
سكريبت لإضافة مستخدمين يدوياً إلى قاعدة البيانات
"""
import asyncio
from app.database import db

async def add_users_manually():
    print("📝 إضافة مستخدمين يدوياً")
    print("=" * 50)
    
    await db.init_models()
    
    users_input = input("\nأدخل قائمة اليوزرات (كل واحد في سطر):\n").strip()
    
    if not users_input:
        print("❌ لم تدخل أي مستخدمين!")
        return
    
    usernames = [line.strip() for line in users_input.split('\n') if line.strip()]
    
    print(f"\n🔄 جاري إضافة {len(usernames)} مستخدم...")
    
    added = 0
    for username in usernames:
        # Remove @ if exists
        clean_username = username.lstrip('@')
        
        # Create fake user_id from username hash
        user_id = abs(hash(clean_username)) % (10**9)
        
        try:
            await db.upsert_user(
                user_id=user_id,
                username=clean_username,
                phone=None,
                last_seen=None,
                country_code=None
            )
            print(f"  ✅ {clean_username}")
            added += 1
        except Exception as e:
            print(f"  ❌ {clean_username}: {e}")
    
    print(f"\n🎉 تم إضافة {added} مستخدم بنجاح!")
    print("الآن يمكنك استخدام 'all' في الإرسال الجماعي")
    
    await db.close()

if __name__ == "__main__":
    asyncio.run(add_users_manually())
