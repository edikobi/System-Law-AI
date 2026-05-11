# Project Map (35 files, 119,568 tokens)
# Root: C:\Users\Admin\fssf-legal-ai test — копия

## (root)/
- `api_manager.py` (2688 tok): Centralized API client for multi-provider AI services (DeepSeek, GigaChat), handling authentication, token management, and SSL configuration for search, generation, and specialized requests.
- `check_docx_styles.py` (1219 tok): Script for automated DOCX document structure analysis using python-docx, generating hierarchical outline reports from paragraph styles.
- `check_structure.py` (1074 tok): Generates a .docx report on legal document structure using DocxLawParser, integrating with pathlib.Path for file and folder operations.
- `config.py` (5783 tok): Configuration management module for legal data paths and environment variables, with utilities for law categorization and display name mapping.
- `main.py` (6965 tok): Orchestration module for a legal AI consultation system that integrates classification, RAG, and document export with both CLI and Telegram bot interfaces.
- `prepare_laws.py` (1208 tok): Legislative document preprocessing pipeline for structured parsing and intelligent chunking, integrating .docx and .txt parsers with encoding support for JSON serialization.
- `run_indexing_and_report.py` (2238 tok): Script for automated document indexing and structural report generation using ChromaDB, processing data from the 'laws' directory.
- `run_structure_analysis.py` (281 tok): Utility module with minimal significant logic.
- `test_deepseek_ping.py` (562 tok): Integration test for DeepSeek API connectivity and performance via APIManager, measuring initialization, request, and response timing through direct deepseek_completion calls.
- `test_parser_report.py` (1146 tok): Unit test suite for DocxIntelligentParser that validates document tree generation and performance metrics, integrating pathlib and datetime for file handling and timestamped reporting.
- `test_report_gen.py` (5395 tok): Automated test suite for RAG-based search validation with integrated DOCX report generation using python-docx, logging, and performance analysis.
- `test_sequential_search(criminal) копия (2)  копия — копия — копия.py` (9525 tok): Automated test suite for sequential legal article search, integrating performance logging, validation, and detailed DOCX report generation via a structured execution pipeline.

## laws/
- `вщ.py` (170 tok): DOCX document structure analyzer using python-docx, extracts style and text from the first 50 non-empty paragraphs for inspection.

## src/
- `__init__.py` (0 tok): Utility module with minimal significant logic.

## src\classification/
- `__init__.py` (0 tok): Utility module with minimal significant logic.
- `deepseek_classifier.py` (722 tok): Legal question classifier using keyword matching and DeepSeek API, integrates with configuration management and API handlers for category determination and query execution.
- `gigachat_classifier.py` (1555 tok): RAG-enhanced classifier using GigaChat and DeepSeek APIs, integrating a configuration manager and API handler for structured text classification.
- `mistral_classifier.py` (736 tok): Legal question classifier using Mistral via Hugging Face API, with keyword-based fallback and configurable settings.

## src\core/
- `__init__.py` (0 tok): Utility module with minimal significant logic.
- `answer_generator.py` (6824 tok): Answer generation system for legal articles with anti-hallucination protection, integrating JSON hints for guidance and psutil for resource monitoring.
- `docx_intelligent_parser.py` (3460 tok): Hierarchical DOCX parser that builds a structured document tree and chunks content by size and outline level, integrating with the docx library for XML-based paragraph analysis.
- `hybrid_navigator.py` (4904 tok): Hybrid legal document retrieval system combining rule-based and semantic search for law chapters, integrating parsing, document reading, and configurable prioritization across code types.
- `law_navigator.py` (7649 tok): Law navigation and analysis system integrating EnhancedLawParser and LegalConceptMapper for parsing legal documents and mapping concepts to structural units.
- `legal_bot.py` (481 tok): Legal question classification and article retrieval system integrating DeepSeekClassifier with SmartRAG for automated legal assistance.
- `legal_bot_simple.py` (1616 tok): Legal question processing system integrating a classifier, law navigator, and DeepSeek for recommendation generation.
- `sequential_searcher.py` (32003 tok): Autonomous legal article search pipeline with RAG-based validation and hierarchical document parsing, integrating with a navigator for container retrieval and answer generation.
- `simple_law_parser.py` (2752 tok): Python parser for semi-structured legal texts using regex and heuristics to extract articles, clauses, and headers, outputting structured data as lists and dictionaries.

## src\rag/
- `__init__.py` (0 tok): Utility module with minimal significant logic.
- `local_semantic_rag.py` (3252 tok): Semantic search and retrieval system for legal documents using ChromaDB and transformer embeddings, integrated with numpy for numerical processing.
- `smart_rag_fixed.py` (2145 tok): Smart RAG system for legal document retrieval using ChromaDB and SentenceTransformer embeddings, integrated with configurable directory paths and legal categories.
- `smart_rag_simple.py` (9142 tok): SmartRAGSystem for legal document retrieval and indexing with ChromaDB and SentenceTransformer, integrated with file parsing and automatic encoding detection.

## src\tools/
- `structure_analyzer.py` (3308 tok): Document structure analyzer for legal documents using python-docx, generating TXT/DOCX reports and integrating with LawNavigator and IntelligentChunkManager for data processing.

## src\utils/
- `__init__.py` (0 tok): Utility module with minimal significant logic.
- `encoding_detector.py` (485 tok): Encoding detection utility using chardet with fallback mechanisms, integrates with file reading workflows for robust text processing.
- `law_utils.py` (280 tok): Law categorization utility that retrieves legislation lists by category, integrating with a Config class for data sourcing and supporting both extended and standard configuration methods.
