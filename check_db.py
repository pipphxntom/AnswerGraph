import asyncio
import sys

# Add proper error handling to detect if there are null bytes in any files
async def check_db_connection():
    try:
        from src.core.db import engine
        from src.models.policy import Policy
        from sqlalchemy import select, text
        from sqlalchemy.ext.asyncio import AsyncSession
        
        print("Successfully imported modules")
        
        # Test database connection
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                print(f"Database connection test: {result.scalar_one() == 1}")
                
                # Get database version
                result = await conn.execute(text("SELECT version()"))
                print(f"Database version: {result.scalar_one()}")
        except Exception as e:
            print(f"Database connection error: {str(e)}")
            
        # Try to query for policies
        try:
            async with AsyncSession(engine) as session:
                stmt = select(Policy)
                result = await session.execute(stmt)
                policies = result.scalars().all()
                print(f"Found {len(policies)} policies in the database")
                
                # Print first policy if any
                if policies:
                    print(f"First policy: {policies[0].id} - {policies[0].title}")
        except Exception as e:
            print(f"Policy query error: {str(e)}")
            
    except UnicodeDecodeError as e:
        print(f"UnicodeDecodeError: {str(e)}")
        print("This may indicate null bytes in source files.")
    except SyntaxError as e:
        print(f"SyntaxError: {str(e)}")
        print("This may indicate null bytes or other syntax issues in source files.")
    except ImportError as e:
        print(f"ImportError: {str(e)}")
        print("This may indicate missing dependencies or issues with the import path.")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        print(f"Error type: {type(e).__name__}")

if __name__ == "__main__":
    asyncio.run(check_db_connection())
