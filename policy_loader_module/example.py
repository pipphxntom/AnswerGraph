"""
Example policy loader usage.

This module demonstrates how to use the policy loader functions in your application code.
"""
import asyncio
import logging
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def example_load_single_policy():
    """Example of loading a single policy JSON file."""
    from policy_loader_module.loader import load_policy_json
    from src.core.db import async_session_factory
    
    policy_path = "data/policies/example_policy.json"
    
    async with async_session_factory() as session:
        try:
            # Load the policy
            policy, procedures, sources = await load_policy_json(policy_path, session)
            
            # Commit the transaction
            await session.commit()
            
            logger.info(f"Successfully loaded policy: {policy.id}")
            logger.info(f"Loaded {len(procedures)} procedures")
            logger.info(f"Loaded {len(sources)} sources")
            
        except Exception as e:
            logger.error(f"Error loading policy: {str(e)}")
            await session.rollback()
            raise


async def example_load_multiple_policies():
    """Example of loading multiple policy JSON files from a directory."""
    from policy_loader_module.loader import load_dir
    
    policies_dir = "data/policies"
    
    try:
        # This handles session management internally
        counts = await load_dir(policies_dir)
        
        logger.info(f"Successfully loaded {counts['policies']} policies")
        logger.info(f"Loaded {counts['procedures']} procedures")
        logger.info(f"Loaded {counts['sources']} sources")
        
        if counts['errors'] > 0:
            logger.warning(f"Encountered {counts['errors']} errors during loading")
            
    except Exception as e:
        logger.error(f"Error loading policies: {str(e)}")
        raise


async def main():
    """Run the example functions."""
    logger.info("Running single policy loading example...")
    await example_load_single_policy()
    
    logger.info("\nRunning multiple policy loading example...")
    await example_load_multiple_policies()


if __name__ == "__main__":
    asyncio.run(main())
