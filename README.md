# PhotoOrg v1.1.0

**Production-ready parallel photo and video organizer**

[![Version](https://img.shields.io/badge/version-1.1.0-blue.svg)](https://github.com/raspitin/PhotoOrg/releases/tag/v1.1.0)
[![License](https://img.shields.io/badge/license-GPL--3.0-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)

## Features

- **Parallel Processing**: 4-8x faster with multi-threading (8-16 worker threads)
- **Smart Organization**: Automatic sorting by year/month directory structure  
- **Duplicate Detection**: SHA-256 hash-based deduplication with zero data loss
- **Database Tracking**: Complete SQLite operation history and statistics
- **High Performance**: 7-24 file/second throughput on multi-core systems
- **Reset Functionality**: Clean reruns with `--reset` command
- **Progress Reporting**: Real-time statistics and processing updates
- **Thread-Safe Operations**: Concurrent file processing with database integrity
- **Configurable**: Extensive YAML configuration for all aspects

## Performance Benchmarks

| System | Files | Time | Throughput | Speedup |
|--------|-------|------|------------|---------|
| 4-core CPU | 420 files | 57s | 7.3 file/s | 1x baseline |
| 4-core CPU | 420 files | 46s | 9.1 file/s | 1.25x optimized |
| 8-core CPU | 1000 files | 42s | 23.8 file/s | ~8x vs single-thread |

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

# Minimum required changes:
# - source: /path/to/your/photos
# - destination: /path/to/organized/output  
# - database: /path/to/database.db
# - log: /path/to/logfile.txt
```

### 3. Usage

```bash
# Activate virtual environment
source venv/bin/activate

# First run - organize photos/videos
python3 PhotoOrg.py

# Reset database and start fresh
python3 PhotoOrg.py --reset

# View help
python3 PhotoOrg.py --help
```

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

### Database Schema

- **files**: Main table with file metadata, paths, hashes, processing info
- **processing_stats**: Session statistics and performance metrics
- **Indexes**: Optimized for hash lookups, media type queries, date ranges

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

### File Types Supported

- **Images**: JPG, PNG, HEIC, TIFF, RAW formats (CR2, NEF, ARW, DNG)
- **Videos**: MP4, MOV, AVI, MKV, M2T, 3GP, WMV, FLV, WEBM
- **Metadata**: EXIF data extraction, filename date parsing
- **Duplicates**: SHA-256 hash comparison, safe duplicate handling

## Advanced Features

### Error Handling

- **Continue on Error**: Processes remaining files even if some fail
- **Retry Logic**: Configurable retry attempts for problematic files
- **Quarantine**: Isolates problematic files for manual review
- **Comprehensive Logging**: Detailed logs with thread information

### Database Features

- **Statistics**: Complete processing statistics and performance metrics
- **Export**: CSV export functionality for reports
- **Cleanup**: Automatic VACUUM and ANALYZE for optimal performance
- **Session Tracking**: Multiple processing session history

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

### Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Follow PEP 8 style guidelines
4. Add tests for new functionality  
5. Update documentation
6. Submit pull request

### Testing

```bash
# Run basic tests
python3 -m pytest tests/

# Performance benchmarking
python3 -m pytest tests/test_performance.py --benchmark-only

# Coverage report
python3 -m pytest --cov=processing tests/
```

### Code Structure

```
PhotoOrg/
├── PhotoOrg.py              # Main entry point
├── config.yaml              # Configuration template
├── processing/              # Core processing modules
│   ├── file_processor.py    # Parallel file processor
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

**First stable release**

**Added:**
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

**Performance:**
- 4-8x speedup on multi-core systems
- 7-24 file/second throughput
- Tested with 420+ files successfully
- Zero data loss in production testing

**Compatibility:**
- Python 3.8+ support
- Linux system compatibility
- UTF-8 encoding support throughout
- Modern file format support (HEIC, WEBP, etc.)

## License

GNU General Public License v3.0 - see [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/PhotoOrg/issues)
- **Documentation**: [Wiki](https://github.com/yourusername/PhotoOrg/wiki)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/PhotoOrg/discussions)

---

**PhotoOrg v1.0.0** - Production-ready photo and video organization with parallel processing.
