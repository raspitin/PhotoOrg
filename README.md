# PhotoOrg v1.2.0

**Production-ready parallel photo and video organizer with dry-run support**

[![Version](https://img.shields.io/badge/version-1.2.0-blue.svg)](https://github.com/raspitin/PhotoOrg/releases/tag/v1.2.0)
[![License](https://img.shields.io/badge/license-GPL--3.0-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)

## Features

- **🚀 Parallel Processing**: 4-8x faster with multi-threading (8-16 worker threads)
- **🎯 Smart Organization**: Automatic sorting by year/month directory structure  
- **🔍 Duplicate Detection**: SHA-256 hash-based deduplication with zero data loss
- **📊 Database Tracking**: Complete SQLite operation history and statistics
- **⚡ High Performance**: 7-24 file/second throughput on multi-core systems
- **🧪 Dry-Run Mode**: Test operations without making any changes (NEW!)
- **🛡️ Safety Controls**: Prevents source=destination accidents (NEW!)
- **🔄 Reset Functionality**: Clean reruns with `--reset` command
- **📈 Progress Reporting**: Real-time statistics and processing updates
- **🔒 Thread-Safe Operations**: Concurrent file processing with database integrity
- **⚙️ Configurable**: Extensive YAML configuration for all aspects

## New in v1.1.0

### 🧪 Dry-Run Mode
Test your configuration and see exactly what would happen without touching any files:

```bash
# Preview what would be organized
python3 PhotoOrg.py --dry-run

# See full analysis without any changes
python3 PhotoOrg.py --dry-run --verbose
```

**Dry-run features:**
- ✅ Full file analysis and organization preview
- ✅ Duplicate detection simulation
- ✅ Database operations in memory only
- ✅ Directory structure preview
- ✅ Performance estimation
- ✅ Zero risk to your files

### 🛡️ Enhanced Safety Controls
Automatic validation prevents dangerous configurations:

- **Source = Destination**: Prevents data loss from identical paths
- **Nested Directories**: Detects and prevents source inside destination or vice versa
- **Path Resolution**: Uses absolute paths to catch symbolic link issues
- **Permission Checks**: Verifies read/write access before starting

## Performance Benchmarks

| System | Files | Time | Throughput | Speedup | Mode |
|--------|-------|------|------------|---------|------|
| 4-core CPU | 420 files | 57s | 7.3 file/s | 1x baseline | Normal |
| 4-core CPU | 420 files | 46s | 9.1 file/s | 1.25x optimized | Normal |
| 8-core CPU | 1000 files | 42s | 23.8 file/s | ~8x vs single-thread | Normal |
| 8-core CPU | 1000 files | 15s | 66.7 file/s | Analysis only | Dry-run |

**Tested Successfully**: 420+ files, zero data loss, multi-year collections (2013-2022)

## Quick Start

### 1. Installation

```bash
# Clone repository
git clone https://github.com/raspitin/PhotoOrg.git
cd PhotoOrg

# Install system dependencies (Ubuntu/Debian)
sudo apt update
sudo apt install python3-gi gir1.2-gexiv2-0.10 libgexiv2-dev mediainfo python3-dev python3-pip python3-venv

# Setup Python environment
./bootstrap.sh
./setup.sh
source venv/bin/activate
```

### 2. Configuration

```bash
# Copy and edit configuration
cp config.yaml.example config.yaml
nano config.yaml

# CRITICAL: Ensure source and destination are different!
# The system will prevent execution if they're identical
```

**Required changes:**
```yaml
source: /path/to/your/photos        # Must exist and be readable
destination: /path/to/organized     # Must be different from source!
database: /path/to/database.db      # SQLite database location
log: /path/to/logfile.txt          # Log file location
```

### 3. Usage

```bash
# Activate virtual environment
source venv/bin/activate

# DRY-RUN: Test configuration first (RECOMMENDED)
python3 PhotoOrg.py --dry-run

# Normal run: organize photos/videos
python3 PhotoOrg.py

# Reset database and start fresh
python3 PhotoOrg.py --reset

# View help
python3 PhotoOrg.py --help
```

## Command Line Options

### Main Operations

```bash
# Standard organization
python3 PhotoOrg.py

# Dry-run mode (simulation only)
python3 PhotoOrg.py --dry-run

# Reset environment
python3 PhotoOrg.py --reset

# Show version
python3 PhotoOrg.py --version

# Show help
python3 PhotoOrg.py --help
```

### Dry-Run Mode Details

The dry-run mode is perfect for:
- **Testing new configurations** before real execution
- **Estimating processing time** for large collections
- **Previewing directory structure** that would be created
- **Identifying potential issues** before they occur
- **Calculating duplicate statistics** without changes
- **Verifying file type detection** accuracy

**What dry-run simulates:**
- ✅ File scanning and analysis
- ✅ Date extraction from EXIF/filename
- ✅ Directory structure creation
- ✅ Duplicate detection
- ✅ Database operations (in memory)
- ✅ Performance statistics

**What dry-run does NOT do:**
- ❌ Copy or move files
- ❌ Create directories on disk
- ❌ Write to permanent database
- ❌ Make any changes to source files

## Architecture

### Parallel Processing Engine

- **ThreadPoolExecutor**: Manages worker thread pool (auto-detects optimal count)
- **Thread-Safe Database**: SQLite with WAL mode for concurrent operations
- **Connection Pooling**: Per-thread database connections with automatic cleanup
- **Progress Tracking**: Real-time statistics with thread-safe counters

### Directory Structure Created

```
destination/
├── PHOTO/
│   ├── 2022/
│   │   ├── 01/
│   │   ├── 02/
│   │   └── ...
│   ├── 2021/
│   └── ...
├── VIDEO/
│   ├── 2022/
│   └── ...
├── PHOTO_DUPLICATES/
├── VIDEO_DUPLICATES/
└── ToReview/
    ├── PHOTO/
    └── VIDEO/
```

### Safety Validations

The system performs comprehensive safety checks:

```python
# Prevents this dangerous configuration:
source: /home/user/photos
destination: /home/user/photos          # ❌ BLOCKED!

# Prevents nested paths:
source: /home/user/photos
destination: /home/user/photos/organized # ❌ BLOCKED!

# Prevents reverse nesting:
source: /home/user/photos/raw
destination: /home/user/photos          # ❌ BLOCKED!

# This is safe:
source: /home/user/photos
destination: /home/user/organized       # ✅ ALLOWED
```

## Configuration Options

### Parallel Processing

```yaml
parallel_processing:
  enabled: true
  max_workers: null          # Auto-detect optimal count
  cpu_multiplier: 2          # Factor for I/O intensive tasks
  max_workers_limit: 16      # Prevent thread explosion
```

### Performance Tuning

```yaml
performance_config:
  batch_size: 100           # Database batch operations
  memory_limit: 1073741824  # 1GB memory limit
  buffer_size: 65536        # 64KB file read buffer
  hash_algorithm: sha256    # Hash algorithm for duplicates
```

### Safety Configuration

```yaml
# Additional safety options
safety_config:
  validate_paths: true      # Enable path validation
  check_permissions: true   # Verify file permissions
  prevent_nested: true      # Block nested source/destination
  require_confirmation: true # Ask before dangerous operations
```

### File Types Supported

- **Images**: JPG, PNG, HEIC, TIFF, RAW formats (CR2, NEF, ARW, DNG)
- **Videos**: MP4, MOV, AVI, MKV, M2T, 3GP, WMV, FLV, WEBM
- **Metadata**: EXIF data extraction, filename date parsing
- **Duplicates**: SHA-256 hash comparison, safe duplicate handling

## Advanced Features

### Dry-Run Workflow

```bash
# 1. First, test your configuration
python3 PhotoOrg.py --dry-run

# 2. Review the output and statistics
# 3. Adjust configuration if needed
# 4. Run dry-run again to verify

# 5. When satisfied, run for real
python3 PhotoOrg.py
```

### Error Handling

- **Continue on Error**: Processes remaining files even if some fail
- **Retry Logic**: Configurable retry attempts for problematic files
- **Quarantine**: Isolates problematic files for manual review
- **Comprehensive Logging**: Detailed logs with thread information
- **Safe Rollback**: Database tracking allows identifying processed files

### Database Features

- **Statistics**: Complete processing statistics and performance metrics
- **Export**: CSV export functionality for reports
- **Cleanup**: Automatic VACUUM and ANALYZE for optimal performance
- **Session Tracking**: Multiple processing session history
- **Dry-run Memory Mode**: In-memory database for safe testing

### Monitoring

- **Real-time Progress**: Updates every N files with statistics
- **Thread Monitoring**: Per-thread performance tracking
- **Memory Usage**: Configurable memory limits and monitoring
- **Performance Metrics**: Throughput, timing, error rates

## Production Deployment

### System Requirements

- **OS**: Linux (Ubuntu 18.04+, Debian 10+, CentOS 7+)
- **Python**: 3.8+ (3.9+ recommended)
- **Memory**: 512MB minimum, 2GB+ recommended for large collections
- **Storage**: Fast SSD recommended for best performance
- **CPU**: Multi-core system for optimal parallel performance

### Pre-deployment Testing

```bash
# Always test with dry-run first
python3 PhotoOrg.py --dry-run

# Check for any configuration issues
python3 PhotoOrg.py --dry-run --verbose

# Test with a small subset first
# (modify source path to point to a small test directory)
python3 PhotoOrg.py --dry-run
python3 PhotoOrg.py

# Only then process the full collection
```

### Scaling Guidelines

```yaml
# For large collections (10,000+ files)
parallel_processing:
  max_workers: 16
  cpu_multiplier: 2

performance_config:
  batch_size: 500
  memory_limit: 2147483648  # 2GB

# For resource-constrained systems
parallel_processing:
  max_workers: 4
  cpu_multiplier: 1

performance_config:
  memory_limit: 536870912   # 512MB
```

## Troubleshooting

### Common Issues

**Configuration errors?**
```bash
# Test configuration with dry-run
python3 PhotoOrg.py --dry-run

# Check for path issues
python3 -c "from pathlib import Path; print(Path('/your/source').resolve())"
```

**"Source and destination are identical" error?**
- Verify paths in config.yaml are different
- Check for symbolic links that might cause path resolution issues
- Use absolute paths to avoid confusion

**Performance too slow?**
- Check `max_workers` setting
- Verify SSD vs HDD storage speed  
- Monitor CPU/memory usage with `htop`
- Reduce `cpu_multiplier` for I/O bound systems

**Database lock errors?**
- Increase `connection_timeout` in database_config
- Check available disk space
- Verify write permissions on database directory

**Memory usage high?**
- Reduce `max_workers` count
- Set `memory_limit` in performance_config  
- Use `cpu_multiplier: 1` to reduce concurrent operations

**GExiv2 import errors?**
- Install: `sudo apt install python3-gi gir1.2-gexiv2-0.10`
- Verify virtual environment: `python3 -c "from gi.repository import GExiv2"`

## Development

### Testing New Features

```bash
# Always use dry-run for testing
python3 PhotoOrg.py --dry-run

# Test with small datasets first
# Test configuration changes
# Test different file types
```

### Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. **Always test with dry-run first**
4. Follow PEP 8 style guidelines
5. Add tests for new functionality  
6. Update documentation
7. Submit pull request

### Code Structure

```
PhotoOrg/
├── PhotoOrg.py              # Main entry point with dry-run support
├── config.yaml              # Configuration template
├── processing/              # Core processing modules
│   ├── file_processor.py    # Parallel file processor (dry-run aware)
│   ├── date_extractor.py    # Metadata extraction
│   ├── hash_utils.py        # Hash calculation
│   └── file_utils.py        # File operations
├── database/                # Database management
│   └── database_manager.py  # Thread-safe database operations
├── loggingSetup/            # Logging configuration
│   └── logging_setup.py     # Log file management
├── config/                  # Configuration management
│   └── config_loader.py     # YAML config loading
└── tests/                   # Test suite
```

## Changelog

### v1.1.0 (2025-01-23)

**Major New Features:**

**🧪 Dry-Run Mode**
- Added `--dry-run` command line option
- Full operation simulation without file modifications
- In-memory database for safe testing
- Comprehensive preview of what would be organized
- Perfect for testing configurations before real execution

**🛡️ Enhanced Safety Controls**
- Automatic detection of identical source/destination paths
- Prevention of nested directory configurations
- Comprehensive path validation with absolute path resolution
- Early detection of permission issues
- Detailed error messages for configuration problems

**🔧 Improved User Experience**
- Better progress reporting with mode indicators
- Enhanced logging with dry-run annotations
- Clearer error messages and warnings
- Improved documentation and examples

**🚀 Performance Improvements**
- Faster dry-run analysis (no file I/O)
- Optimized path validation
- Better memory usage in simulation mode

**🐛 Bug Fixes**
- Fixed potential issues with symbolic links
- Improved error handling for edge cases
- Better cleanup of resources in all modes

**Previous Features (v1.0.0):**
- Parallel file processing with ThreadPoolExecutor
- Thread-safe SQLite database operations
- Automatic duplicate detection and handling
- Configurable worker thread management
- Real-time progress tracking and statistics
- Year/month directory organization structure
- Comprehensive error handling and recovery
- Performance optimizations and tuning options
- Complete logging and audit trail
- Reset functionality for clean reruns

## License

GNU General Public License v3.0 - see [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/PhotoOrg/issues)
- **Documentation**: [Wiki](https://github.com/yourusername/PhotoOrg/wiki)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/PhotoOrg/discussions)

---

**PhotoOrg v1.1.0** - Production-ready photo and video organization with parallel processing and dry-run safety.

### 🎯 Quick Start Checklist

- [ ] Install system dependencies
- [ ] Configure source and destination paths (ensure they're different!)
- [ ] **Run dry-run first**: `python3 PhotoOrg.py --dry-run`
- [ ] Review dry-run output and adjust configuration if needed
- [ ] Run real organization: `python3 PhotoOrg.py`
- [ ] Check results and statistics
