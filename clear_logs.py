#!/usr/bin/env python3
"""
سكريبت لمسح سجلات الرسائل المرسلة
هذا يسمح بإعادة الإرسال لنفس الأشخاص
"""
import asyncio
from app.database import db
from sqlalchemy import select, func
from app.database import MessageLog

async def clear_message_logs():
    print("🗑️  مسح سجلات الرسائل المرسلة")
    print("=" * 50)
    
    await db.init_models()
    
    # Count current logs
    async with db.session() as session:
        result = await session.execute(select(func.count()).select_from(MessageLog))
        count = result.scalar()
    
    print(f"\n📊 عدد السجلات الحالية: {count}")
    
    if count == 0:
        print("✅ لا يوجد سجلات للمسح")
        await db.close()
        return
    
    confirm = input("\n⚠️  هل أنت متأكد من مسح جميع السجلات؟ (yes/no): ").strip().lower()
    
    if confirm in ['yes', 'y', 'نعم']:
        async with db.session() as session:
            from sqlalchemy import delete
            await session.execute(delete(MessageLog))
            await session.commit()
        
        print("\n✅ تم مسح جميع السجلات بنجاح!")
        print("الآن يمكنك إعادة الإرسال لنفس الأشخاص")
    else:
        print("\n❌ تم إلغاء العملية")
    
    await db.close()

if __name__ == "__main__":
    asyncio.run(clear_message_logs())
