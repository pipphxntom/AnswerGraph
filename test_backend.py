"""
A2G Backend Comprehensive Diagnostic Tool

This script performs systematic diagnostics on the A2G backend system to identify and 
resolve configuration, data integrity, and dependency issues.

Author: CTO, A2G Project
Date: August 29, 2025
"""
import asyncio
import logging
import os
import sys
import traceback
import importlib
import pkgutil
import io
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("a2g_diagnostics")

class DiagnosticResult:
    """Class to store the result of a diagnostic test."""
    def __init__(self, name: str, status: bool, message: str, details: Any = None):
        self.name = name
        self.status = status  # True = passed, False = failed
        self.message = message
        self.details = details
        self.timestamp = import_safe_datetime_now()
    
    def __str__(self):
        status_str = "✅ PASSED" if self.status else "❌ FAILED"
        return f"{self.name}: {status_str} - {self.message}"

def import_safe_datetime_now():
    """Get current datetime with fallback for import errors."""
    try:
        from datetime import datetime
        return datetime.now()
    except ImportError:
        return None

async def check_python_environment() -> DiagnosticResult:
    """Check Python environment for compatibility issues."""
    try:
        # Check Python version
        python_version = sys.version
        version_info = sys.version_info
        
        if version_info.major < 3 or (version_info.major == 3 and version_info.minor < 8):
            return DiagnosticResult(
                "Python Environment", 
                False,
                f"Python version {python_version} is too old. Required: 3.8+",
                {"version": python_version}
            )
        
        # Check working directory
        cwd = os.getcwd()
        
        # Check if the current working directory has the expected structure
        expected_dirs = ["src", "tests", "docs"]
        missing_dirs = [d for d in expected_dirs if not os.path.isdir(os.path.join(cwd, d))]
        
        if missing_dirs:
            return DiagnosticResult(
                "Python Environment", 
                False,
                f"Working directory {cwd} is missing expected directories: {', '.join(missing_dirs)}",
                {"cwd": cwd, "missing_dirs": missing_dirs}
            )
        
        return DiagnosticResult(
            "Python Environment", 
            True,
            f"Python environment is compatible: {python_version}, working directory: {cwd}",
            {"version": python_version, "cwd": cwd}
        )
    except Exception as e:
        return DiagnosticResult(
            "Python Environment", 
            False,
            f"Failed to check Python environment: {str(e)}",
            {"error": str(e), "traceback": traceback.format_exc()}
        )

async def check_dependencies() -> DiagnosticResult:
    """Check if all required dependencies are installed and compatible."""
    try:
        missing_deps = []
        version_issues = []
        
        # Check core dependencies
        dependencies = [
            ("fastapi", "0.103.0"),
            ("uvicorn", "0.23.0"),
            ("sqlalchemy", "2.0.0"),
            ("pydantic", "2.0.0"),
            ("sentence-transformers", "2.2.0"),
            ("qdrant-client", "1.6.0"),
            ("transformers", "4.36.0"),
            ("torch", "2.0.0"),
        ]
        
        for package_name, min_version in dependencies:
            try:
                package = importlib.import_module(package_name)
                if hasattr(package, "__version__"):
                    installed_version = package.__version__
                    # Very basic version comparison - in production use packaging.version
                    if installed_version.split(".")[0] < min_version.split(".")[0]:
                        version_issues.append((package_name, installed_version, min_version))
                else:
                    # Can't determine version, assume it's OK
                    pass
            except ImportError:
                missing_deps.append(package_name)
        
        if missing_deps or version_issues:
            issues = []
            if missing_deps:
                issues.append(f"Missing dependencies: {', '.join(missing_deps)}")
            if version_issues:
                issues.append(f"Version issues: {', '.join([f'{p}({i}<{m})' for p, i, m in version_issues])}")
            
            return DiagnosticResult(
                "Dependencies", 
                False,
                "Dependency issues detected",
                {"missing": missing_deps, "version_issues": version_issues}
            )
        
        return DiagnosticResult(
            "Dependencies", 
            True,
            "All required dependencies are installed and compatible",
            {"checked_packages": [d[0] for d in dependencies]}
        )
    except Exception as e:
        return DiagnosticResult(
            "Dependencies", 
            False,
            f"Failed to check dependencies: {str(e)}",
            {"error": str(e), "traceback": traceback.format_exc()}
        )

async def check_file_integrity() -> DiagnosticResult:
    """Check for file corruption issues like null bytes in Python files."""
    try:
        problematic_files = []
        
        # Walk through the src directory
        src_dir = os.path.join(os.getcwd(), "src")
        
        for root, dirs, files in os.walk(src_dir):
            for file in files:
                if file.endswith(".py"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "rb") as f:
                            content = f.read()
                            if b"\x00" in content:  # Check for null bytes
                                problematic_files.append({
                                    "path": file_path,
                                    "issue": "Contains null bytes",
                                    "fixable": True
                                })
                    except Exception as file_error:
                        problematic_files.append({
                            "path": file_path,
                            "issue": f"Error reading file: {str(file_error)}",
                            "fixable": False
                        })
        
        if problematic_files:
            return DiagnosticResult(
                "File Integrity", 
                False,
                f"Found {len(problematic_files)} problematic files",
                {"problematic_files": problematic_files}
            )
        
        return DiagnosticResult(
            "File Integrity", 
            True,
            "All Python files passed integrity checks",
            {}
        )
    except Exception as e:
        return DiagnosticResult(
            "File Integrity", 
            False,
            f"Failed to check file integrity: {str(e)}",
            {"error": str(e), "traceback": traceback.format_exc()}
        )

async def check_config() -> DiagnosticResult:
    """Check configuration settings."""
    try:
        # Try to import config
        try:
            from src.core.config import get_settings
            settings = get_settings()
            
            # Check required settings
            required_fields = [
                "app_name", "database_url", "qdrant_url", "embeddings_model"
            ]
            
            missing_fields = []
            for field in required_fields:
                if not hasattr(settings, field) or getattr(settings, field) is None or getattr(settings, field) == "":
                    missing_fields.append(field)
            
            if missing_fields:
                return DiagnosticResult(
                    "Configuration", 
                    False,
                    f"Missing required configuration fields: {', '.join(missing_fields)}",
                    {"missing_fields": missing_fields}
                )
            
            # Check database URL format
            db_url = settings.database_url
            if not db_url.startswith(("postgresql://", "postgresql+asyncpg://")):
                return DiagnosticResult(
                    "Configuration", 
                    False,
                    f"Invalid database URL format: {db_url}",
                    {"database_url": db_url}
                )
            
            return DiagnosticResult(
                "Configuration", 
                True,
                "All configuration settings are valid",
                {field: getattr(settings, field) for field in required_fields if hasattr(settings, field)}
            )
        except ImportError:
            return DiagnosticResult(
                "Configuration", 
                False,
                "Failed to import configuration module",
                {"error": "Import error"}
            )
    except Exception as e:
        return DiagnosticResult(
            "Configuration", 
            False,
            f"Failed to check configuration: {str(e)}",
            {"error": str(e), "traceback": traceback.format_exc()}
        )

async def check_database_connection() -> DiagnosticResult:
    """Check database connection."""
    try:
        try:
            # First try importing the db module directly
            from src.core.db import get_engine, get_session
            
            # Test connection with a simple query
            engine = get_engine()
            async with get_session() as session:
                result = await session.execute("SELECT 1")
                value = result.scalar()
                
                if value != 1:
                    return DiagnosticResult(
                        "Database Connection", 
                        False,
                        "Database query returned unexpected result",
                        {"result": value}
                    )
                
                # Try more complex query to check tables
                try:
                    result = await session.execute("SELECT COUNT(*) FROM policy")
                    policy_count = result.scalar()
                    
                    result = await session.execute("SELECT COUNT(*) FROM source")
                    source_count = result.scalar()
                    
                    return DiagnosticResult(
                        "Database Connection", 
                        True,
                        f"Database connection successful. Found {policy_count} policies and {source_count} sources.",
                        {"policy_count": policy_count, "source_count": source_count}
                    )
                except Exception as query_error:
                    # Tables might not exist yet
                    return DiagnosticResult(
                        "Database Connection", 
                        True,
                        "Database connection successful, but schema might not be initialized",
                        {"error": str(query_error)}
                    )
        except ImportError:
            # Try alternative approach with SQLAlchemy directly
            try:
                from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
                from sqlalchemy.orm import sessionmaker
                from src.core.config import get_settings
                
                settings = get_settings()
                engine = create_async_engine(settings.database_url)
                async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
                
                async with async_session() as session:
                    result = await session.execute("SELECT 1")
                    value = result.scalar()
                    
                    if value != 1:
                        return DiagnosticResult(
                            "Database Connection", 
                            False,
                            "Database query returned unexpected result",
                            {"result": value}
                        )
                    
                    return DiagnosticResult(
                        "Database Connection", 
                        True,
                        "Database connection successful using direct SQLAlchemy approach",
                        {}
                    )
            except ImportError:
                return DiagnosticResult(
                    "Database Connection", 
                    False,
                    "Failed to import necessary database modules",
                    {"error": "Import error"}
                )
            except Exception as direct_error:
                return DiagnosticResult(
                    "Database Connection", 
                    False,
                    f"Failed to connect to database using direct approach: {str(direct_error)}",
                    {"error": str(direct_error)}
                )
    except Exception as e:
        return DiagnosticResult(
            "Database Connection", 
            False,
            f"Failed to check database connection: {str(e)}",
            {"error": str(e), "traceback": traceback.format_exc()}
        )

async def check_vector_db_connection() -> DiagnosticResult:
    """Check connection to the vector database (Qdrant)."""
    try:
        try:
            from src.core.dependencies import get_qdrant_client
            
            client = get_qdrant_client()
            collections = client.get_collections()
            
            return DiagnosticResult(
                "Vector DB Connection", 
                True,
                f"Successfully connected to Qdrant. Collections: {[c.name for c in collections.collections]}",
                {"collections": [c.name for c in collections.collections]}
            )
        except ImportError:
            # Try direct approach
            try:
                from qdrant_client import QdrantClient
                from src.core.config import get_settings
                
                settings = get_settings()
                
                if settings.qdrant_url.startswith(("http://", "https://")):
                    # HTTP connection
                    parts = settings.qdrant_url.split(":")
                    if len(parts) == 3:  # http://host:port
                        host = parts[1].strip("/")
                        port = int(parts[2])
                        client = QdrantClient(host=host, port=port)
                    else:
                        client = QdrantClient(url=settings.qdrant_url)
                else:
                    # Local path
                    client = QdrantClient(path=settings.qdrant_url)
                
                collections = client.get_collections()
                
                return DiagnosticResult(
                    "Vector DB Connection", 
                    True,
                    f"Successfully connected to Qdrant using direct approach. Collections: {[c.name for c in collections.collections]}",
                    {"collections": [c.name for c in collections.collections]}
                )
            except ImportError:
                return DiagnosticResult(
                    "Vector DB Connection", 
                    False,
                    "Failed to import necessary vector DB modules",
                    {"error": "Import error"}
                )
            except Exception as direct_error:
                return DiagnosticResult(
                    "Vector DB Connection", 
                    False,
                    f"Failed to connect to Qdrant using direct approach: {str(direct_error)}",
                    {"error": str(direct_error)}
                )
    except Exception as e:
        return DiagnosticResult(
            "Vector DB Connection", 
            False,
            f"Failed to check vector DB connection: {str(e)}",
            {"error": str(e), "traceback": traceback.format_exc()}
        )

async def check_embeddings_model() -> DiagnosticResult:
    """Check if the embeddings model can be loaded and used."""
    try:
        try:
            from src.core.dependencies import get_embedding_model
            
            model = get_embedding_model()
            
            # Test with a simple sentence
            test_text = "This is a test sentence for embeddings."
            embedding = model.encode(test_text)
            
            # Check embedding dimensions
            if len(embedding.shape) != 1 or embedding.shape[0] < 10:
                return DiagnosticResult(
                    "Embeddings Model", 
                    False,
                    f"Embedding model returned unexpected dimensions: {embedding.shape}",
                    {"shape": embedding.shape}
                )
            
            return DiagnosticResult(
                "Embeddings Model", 
                True,
                f"Successfully loaded embeddings model. Embedding dimensions: {embedding.shape}",
                {"dimensions": embedding.shape[0], "model_info": str(model)}
            )
        except ImportError:
            # Try direct approach
            try:
                from sentence_transformers import SentenceTransformer
                from src.core.config import get_settings
                
                settings = get_settings()
                model = SentenceTransformer(settings.embeddings_model)
                
                # Test with a simple sentence
                test_text = "This is a test sentence for embeddings."
                embedding = model.encode(test_text)
                
                return DiagnosticResult(
                    "Embeddings Model", 
                    True,
                    f"Successfully loaded embeddings model using direct approach. Embedding dimensions: {embedding.shape}",
                    {"dimensions": embedding.shape[0], "model_name": settings.embeddings_model}
                )
            except ImportError:
                return DiagnosticResult(
                    "Embeddings Model", 
                    False,
                    "Failed to import necessary embeddings modules",
                    {"error": "Import error"}
                )
            except Exception as direct_error:
                return DiagnosticResult(
                    "Embeddings Model", 
                    False,
                    f"Failed to load embeddings model using direct approach: {str(direct_error)}",
                    {"error": str(direct_error)}
                )
    except Exception as e:
        return DiagnosticResult(
            "Embeddings Model", 
            False,
            f"Failed to check embeddings model: {str(e)}",
            {"error": str(e), "traceback": traceback.format_exc()}
        )

async def fix_null_bytes() -> DiagnosticResult:
    """Fix null bytes in Python files."""
    try:
        fixed_files = []
        failed_files = []
        
        # Get list of problematic files from check_file_integrity
        file_check_result = await check_file_integrity()
        
        if not file_check_result.status:
            problematic_files = file_check_result.details.get("problematic_files", [])
            
            for file_info in problematic_files:
                if file_info["fixable"]:
                    try:
                        file_path = file_info["path"]
                        with open(file_path, "rb") as f:
                            content = f.read()
                        
                        # Remove null bytes
                        fixed_content = content.replace(b"\x00", b"")
                        
                        with open(file_path, "wb") as f:
                            f.write(fixed_content)
                        
                        fixed_files.append(file_path)
                    except Exception as fix_error:
                        failed_files.append({
                            "path": file_path,
                            "error": str(fix_error)
                        })
        
        if fixed_files:
            return DiagnosticResult(
                "Fix Null Bytes", 
                True,
                f"Successfully fixed {len(fixed_files)} files with null bytes",
                {"fixed_files": fixed_files, "failed_files": failed_files}
            )
        elif failed_files:
            return DiagnosticResult(
                "Fix Null Bytes", 
                False,
                f"Failed to fix {len(failed_files)} files with null bytes",
                {"failed_files": failed_files}
            )
        else:
            return DiagnosticResult(
                "Fix Null Bytes", 
                True,
                "No files with null bytes found",
                {}
            )
    except Exception as e:
        return DiagnosticResult(
            "Fix Null Bytes", 
            False,
            f"Failed to fix null bytes: {str(e)}",
            {"error": str(e), "traceback": traceback.format_exc()}
        )

async def test_guards() -> DiagnosticResult:
    """Test the guards system functionality."""
    try:
        from src.rag.guards import require_citation, numeric_consistency, staleness_guard, disambiguation_guard, apply_guards
        
        # Test citation guard
        test_contract_rag = {
            "text": "The fee deadline is April 30, 2025.",
            "source": {
                "url": "http://example.com/policies/fees",
                "page": 10,
                "updated_at": "2024-08-01"
            }
        }
        
        citation_passed, citation_msg = require_citation(test_contract_rag)
        
        # Test rules path format
        test_contract_rules = {
            "text": "The fee deadline is April 30, 2025.",
            "sources": [
                {
                    "url": "http://example.com/policies/fees",
                    "page": 10,
                    "updated_at": "2024-08-01"
                }
            ]
        }
        
        citation_rules_passed, citation_rules_msg = require_citation(test_contract_rules)
        
        # Test numeric consistency
        answer_text = "The policy states a limit of $5,000 and a timeframe of 30 days."
        evidence_texts = ["According to section 3.2, there is a maximum limit of $5,000.", 
                          "The standard timeframe is 30 days from submission."]
        num_passed, num_msg, missing = numeric_consistency(answer_text, evidence_texts)
        
        # Test staleness guard
        staleness_passed, staleness_msg = staleness_guard("2024-08-01", 365)
        
        # Test apply_guards
        guard_results = []
        try:
            passed, reasons, details = await apply_guards(
                answer_contract=test_contract_rag,
                evidence_texts=evidence_texts,
                guards_to_apply=["citation", "staleness", "numeric"]
            )
            guard_results.append(("apply_guards", passed, reasons))
        except Exception as apply_error:
            guard_results.append(("apply_guards", False, str(apply_error)))
        
        all_passed = (citation_passed and citation_rules_passed and num_passed and staleness_passed and 
                      all(result[1] for result in guard_results))
        
        return DiagnosticResult(
            "Guards System", 
            all_passed,
            "Guards system diagnostic complete",
            {
                "citation_guard": {"passed": citation_passed, "message": citation_msg},
                "citation_rules_guard": {"passed": citation_rules_passed, "message": citation_rules_msg},
                "numeric_consistency": {"passed": num_passed, "message": num_msg, "missing": missing},
                "staleness_guard": {"passed": staleness_passed, "message": staleness_msg},
                "apply_guards_results": guard_results
            }
        )
    except ImportError as import_error:
        return DiagnosticResult(
            "Guards System", 
            False,
            f"Failed to import guards modules: {str(import_error)}",
            {"error": str(import_error)}
        )
    except Exception as e:
        return DiagnosticResult(
            "Guards System", 
            False,
            f"Failed to test guards system: {str(e)}",
            {"error": str(e), "traceback": traceback.format_exc()}
        )

async def test_language_processing() -> DiagnosticResult:
    """Test language processing functionality."""
    try:
        try:
            from src.nlp.lang import process_query, detect_lang, normalize_hinglish
            
            results = []
            
            # Test English query
            english_query = "What is the fee deadline for BTech program?"
            english_result = process_query(english_query)
            results.append(("English", english_result))
            
            # Test Hinglish query if available
            try:
                hinglish_query = "BTech ki fees deadline kya hai?"
                hinglish_result = process_query(hinglish_query)
                results.append(("Hinglish", hinglish_result))
                
                # Test normalization directly
                normalized = normalize_hinglish(hinglish_query)
                results.append(("Hinglish Normalization", normalized))
            except Exception as hinglish_error:
                results.append(("Hinglish", {"error": str(hinglish_error)}))
            
            # Test language detection directly
            try:
                en_lang = detect_lang(english_query)
                results.append(("Language Detection (English)", en_lang))
                
                if 'hinglish_query' in locals():
                    hi_lang = detect_lang(hinglish_query)
                    results.append(("Language Detection (Hinglish)", hi_lang))
            except Exception as detect_error:
                results.append(("Language Detection", {"error": str(detect_error)}))
            
            return DiagnosticResult(
                "Language Processing", 
                True,
                "Language processing diagnostic complete",
                {"results": results}
            )
        except ImportError:
            return DiagnosticResult(
                "Language Processing", 
                False,
                "Failed to import language processing modules",
                {"error": "Import error"}
            )
    except Exception as e:
        return DiagnosticResult(
            "Language Processing", 
            False,
            f"Failed to test language processing: {str(e)}",
            {"error": str(e), "traceback": traceback.format_exc()}
        )

async def run_diagnostics():
    """Run all diagnostics and return results."""
    logger.info("=" * 60)
    logger.info("A2G Backend Comprehensive Diagnostic Tool")
    logger.info("=" * 60)
    
    # Step 1: Check Python environment
    logger.info("\n[1/10] Checking Python environment...")
    env_result = await check_python_environment()
    logger.info(str(env_result))
    
    # Step 2: Check dependencies
    logger.info("\n[2/10] Checking dependencies...")
    dep_result = await check_dependencies()
    logger.info(str(dep_result))
    
    # Step 3: Check file integrity
    logger.info("\n[3/10] Checking file integrity...")
    file_result = await check_file_integrity()
    logger.info(str(file_result))
    
    # Step 4: Fix null bytes if needed
    if not file_result.status:
        logger.info("\n[4/10] Fixing files with null bytes...")
        fix_result = await fix_null_bytes()
        logger.info(str(fix_result))
    else:
        logger.info("\n[4/10] Skipping fix for null bytes (not needed)")
        fix_result = DiagnosticResult("Fix Null Bytes", True, "No fixes needed", {})
    
    # Step 5: Check configuration
    logger.info("\n[5/10] Checking configuration...")
    config_result = await check_config()
    logger.info(str(config_result))
    
    # Step 6: Check database connection
    logger.info("\n[6/10] Checking database connection...")
    db_result = await check_database_connection()
    logger.info(str(db_result))
    
    # Step 7: Check vector DB connection
    logger.info("\n[7/10] Checking vector database connection...")
    vector_result = await check_vector_db_connection()
    logger.info(str(vector_result))
    
    # Step 8: Check embeddings model
    logger.info("\n[8/10] Checking embeddings model...")
    embed_result = await check_embeddings_model()
    logger.info(str(embed_result))
    
    # Step 9: Test guards system
    logger.info("\n[9/10] Testing guards system...")
    guards_result = await test_guards()
    logger.info(str(guards_result))
    
    # Step 10: Test language processing
    logger.info("\n[10/10] Testing language processing...")
    lang_result = await test_language_processing()
    logger.info(str(lang_result))
    
    # Collect all results
    results = [
        env_result, dep_result, file_result, fix_result,
        config_result, db_result, vector_result, embed_result,
        guards_result, lang_result
    ]
    
    # Print summary
    passed = sum(1 for r in results if r.status)
    total = len(results)
    
    logger.info("\n" + "=" * 60)
    logger.info(f"DIAGNOSTIC SUMMARY: {passed}/{total} checks passed")
    logger.info("=" * 60)
    
    for result in results:
        status_str = "✅ PASSED" if result.status else "❌ FAILED"
        logger.info(f"{result.name}: {status_str}")
    
    # Provide recommendations based on results
    logger.info("\n" + "=" * 60)
    logger.info("RECOMMENDATIONS")
    logger.info("=" * 60)
    
    if not env_result.status:
        logger.info("- Update Python to version 3.8 or higher")
    
    if not dep_result.status:
        missing = dep_result.details.get("missing", [])
        version_issues = dep_result.details.get("version_issues", [])
        
        if missing:
            deps_str = ", ".join(missing)
            logger.info(f"- Install missing dependencies: pip install {deps_str}")
        
        if version_issues:
            for package, installed, required in version_issues:
                logger.info(f"- Update {package} from {installed} to at least {required}")
    
    if not file_result.status and not fix_result.status:
        logger.info("- Manually fix files with null bytes that couldn't be automatically fixed")
    
    if not config_result.status:
        missing_fields = config_result.details.get("missing_fields", [])
        if missing_fields:
            logger.info(f"- Update configuration to include: {', '.join(missing_fields)}")
    
    if not db_result.status:
        logger.info("- Check database connection string and ensure database server is running")
    
    if not vector_result.status:
        logger.info("- Check Qdrant connection settings and ensure Qdrant server is running")
    
    if not embed_result.status:
        logger.info("- Check embeddings model configuration and ensure model files are accessible")
    
    if not guards_result.status:
        logger.info("- Review guards implementation for errors")
    
    if not lang_result.status:
        logger.info("- Check language processing modules and ensure required models are installed")
    
    if all(r.status for r in results):
        logger.info("✅ All systems operational! No action needed.")
    
    return results

async def main():
    """Run the backend diagnostics."""
    try:
        await run_diagnostics()
    except Exception as e:
        logger.error(f"Diagnostic failed with exception: {str(e)}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main())
