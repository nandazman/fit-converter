# 🏊 SwimFlow - Advanced Swimming OCR Analytics

A sophisticated **FastAPI + Tesseract** service that extracts and analyzes swimming segment data from **Huawei Health → Pool Swim → Segments** screenshots with advanced image processing and lap detection capabilities.

## ✨ Features

- **Advanced Image Processing** with lap boundary detection and segmentation
- **Split-then-OCR Method** for improved accuracy on complex swimming data
- **REST API** with endpoints for image splitting and segment processing
- **Beautiful UI** with crop tools, segment visualization, and real-time feedback
- **CSV Export** with detailed swimming metrics and performance data
- **Nginx** reverse proxy for secure access
- **Systemd** service management
- **GitHub Actions CI/CD** for automated deployment

## 🚀 Quick Start

### Prerequisites

- Ubuntu server (2 vCPU, 2 GB RAM, 40 GB disk)
- Python 3.10+
- Tesseract OCR
- Nginx

### One-time Server Setup

```bash
# Install system dependencies
sudo apt update
sudo apt install -y tesseract-ocr libtesseract-dev python3-venv nginx

# Create app directory
sudo mkdir -p /opt/swim-ocr
sudo chown -R $USER:$USER /opt/swim-ocr
```

### Local Development

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd fit-converter
   ```

2. **Install dependencies**
   ```bash
   # Install system dependencies (Ubuntu/Debian)
   sudo apt install tesseract-ocr libtesseract-dev
   
   # Install Python dependencies
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   # Start the FastAPI server
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

4. **Access the UI**
   - Open your browser to `http://localhost:8000/static/index.html`
   - Upload a Huawei Health swimming screenshot
   - Get extracted JSON data and CSV download

## 📁 Project Structure

```
fit-converter/
├── app/
│   ├── main.py                     # FastAPI application entry point
│   ├── api/
│   │   └── routes.py               # API route handlers
│   ├── helpers/
│   │   ├── utils.py                # Utility functions
│   │   └── storage.py              # Temporary storage management
│   ├── ocr/
│   │   └── text_extractor.py       # OCR processing logic
│   └── image_processing/
│       ├── image_splitter.py       # Image segmentation logic
│       ├── lap_detection.py        # Lap boundary detection
│       └── preprocessing.py        # Image preprocessing utilities
├── static/
│   └── index.html                  # Advanced UI with crop tools and visualization
├── .github/workflows/
│   └── deploy.yml                  # GitHub Actions CI/CD
├── requirements.txt                # Python dependencies
├── run.sh                         # Development server script
├── deploy.sh                      # Manual deployment script
├── setup.sh                       # System setup script
├── README.md                      # This file
└── REQUIREMENTS.md                # Detailed requirements
```

## 🔧 API Endpoints

### Core Processing Endpoints

#### `POST /api/split`
Split image into segments and return segment information without OCR processing.

**Request:**
- `multipart/form-data` with `file` field
- Supported formats: PNG, JPG, JPEG, WEBP, BMP
- Max file size: 20MB

**Response:**
```json
{
  "split_id": "uuid-string",
  "total_segments": 5,
  "segment_info": [...]
}
```

#### `GET /api/segment/{segment_id}`
Get individual segment image after splitting.

#### `POST /api/ocr-segment/{segment_id}`
OCR a single segment image.

**Response:**
```json
{
  "segment_id": "split_id_0",
  "segment": {
    "laps": [
      {
        "lap": 1,
        "stroke_type": "Breaststroke",
        "lap_length_m": 50,
        "duration": "2:28",
        "strokes": 37,
        "swolf": 185,
        "pace_per_100m": "4:56"
      }
    ]
  },
  "info": {...}
}
```

### Utility Endpoints

#### `GET /healthz`
Health check endpoint.

## 🎨 UI Features

- **Advanced Image Cropping** with interactive crop tool
- **Drag & Drop** file upload with visual feedback
- **Real-time** processing with progress indicators
- **Segment Visualization** showing extracted lap boundaries
- **Debug Image Overlay** with boundary detection visualization
- **JSON preview** of extracted data with syntax highlighting
- **CSV download** functionality with formatted metrics
- **Responsive design** optimized for mobile and desktop
- **Error handling** with detailed user-friendly messages
- **Split & Analyze** workflow for complex swimming data

## 🚀 Deployment

### Manual Deployment

1. **Run the deployment script**
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

2. **Access your app**
   - UI: `http://your-server-ip/swim/`
   - Health: `http://your-server-ip/healthz`

### Automated Deployment (GitHub Actions)

1. **Set up repository secrets:**
   - `DEPLOY_HOST` → Your server IP or domain
   - `DEPLOY_USER` → SSH username (e.g., `ubuntu`)
   - `DEPLOY_SSH_KEY` → Private SSH key

2. **Push to main branch**
   ```bash
   git add .
   git commit -m "Deploy swim OCR app"
   git push origin main
   ```

The GitHub Action will automatically:
- Run tests
- Deploy to your server
- Configure Nginx
- Start the systemd service

## 🔍 How It Works

1. **Image Upload**: User uploads a Huawei Health swimming screenshot
2. **Image Splitting**: Advanced algorithm detects lap boundaries and splits image into segments
3. **Segment Processing**: Each segment is processed individually for better OCR accuracy
4. **OCR Processing**: Tesseract extracts text from each segment
5. **Data Extraction**: Regex patterns extract swimming metrics:
   - Lap number
   - Stroke type (Breaststroke, Freestyle, etc.)
   - Length (50m, 100m, etc.)
   - Duration (in seconds)
   - Stroke count
   - SWOLF score
   - Pace per 100m
6. **Response**: Returns structured JSON with all extracted data and CSV download

## 📊 Extracted Data Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `lap` | int | Lap number | 1 |
| `stroke_type` | string | Swimming stroke | "Breaststroke" |
| `lap_length_m` | int | Distance in meters | 50 |
| `duration_sec` | int | Time in seconds | 148 |
| `strokes` | int | Number of strokes | 37 |
| `swolf` | int | SWOLF score | 185 |
| `pace_per_100m_sec` | int | Pace in seconds/100m | 296 |

## 🛠️ Configuration

### Nginx Configuration
The app uses Nginx as a reverse proxy:
- `/swim/` → Static UI files
- `/api/` → FastAPI backend
- `/healthz` → Health check

### Systemd Service
The FastAPI app runs as a systemd service with auto-restart on failure.

## 🧪 Testing

```bash
# Test imports
python -c "import app.main; print('✅ App imports successfully')"

# Test dependencies
python -c "import cv2, pytesseract, fastapi; print('✅ All dependencies available')"

# Run with pytest (if you add tests)
pytest
```

## 🔧 Troubleshooting

### Common Issues

1. **Tesseract not found**
   ```bash
   sudo apt install tesseract-ocr libtesseract-dev
   ```

2. **Permission denied**
   ```bash
   sudo chown -R $USER:$USER /opt/swim-ocr
   ```

3. **Service not starting**
   ```bash
   sudo systemctl status swim-ocr
   sudo journalctl -u swim-ocr -f
   ```

4. **Nginx configuration**
   ```bash
   sudo nginx -t
   sudo systemctl reload nginx
   ```

### Logs

```bash
# Application logs
sudo journalctl -u swim-ocr -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## 📝 Example Usage

1. **Take a screenshot** of your Huawei Health app showing swimming segments
2. **Upload the image** to the web interface
3. **Get structured data** in JSON format
4. **Download CSV** for further analysis

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is open source and available under the MIT License.

## 🆘 Support

If you encounter any issues:
1. Check the troubleshooting section
2. Review the logs
3. Open an issue on GitHub

---

**Happy Swimming! 🏊‍♀️🏊‍♂️**
