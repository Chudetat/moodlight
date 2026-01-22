# Dopa - Biometric Event Measurement Platform

Dopa measures collective emotional engagement at events through heart rate data from wearable devices.

## Features

- **Event Management**: Create events and generate QR codes for participant opt-in
- **Oura Integration**: OAuth flow to connect participants' Oura Rings
- **Heart Rate Tracking**: Collect and aggregate heart rate data during events
- **Peak Detection**: Identify moments of high collective engagement
- **PDF Reports**: Generate post-event reports with timeline and peak moments

## Quick Start

### 1. Install dependencies

```bash
cd dopa
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your Oura OAuth credentials
```

### 3. Get Oura API credentials

1. Go to [Oura Cloud](https://cloud.ouraring.com/oauth/applications)
2. Create a new application
3. Set redirect URI to `http://localhost:8000/auth/oura/callback`
4. Copy Client ID and Secret to your `.env`

### 4. Run the server

```bash
uvicorn app.main:app --reload
```

Visit http://localhost:8000 for the API, or http://localhost:8000/docs for interactive documentation.

## API Endpoints

### Events
- `POST /api/events` - Create a new event
- `GET /api/events` - List all events
- `GET /api/events/{id}` - Get event details with QR code URL
- `GET /api/events/{id}/qr` - Download QR code image

### Participants
- `POST /api/participants/event/{opt_in_code}` - Register for an event
- `GET /api/participants/event/{event_id}` - List event participants
- `POST /api/participants/{id}/sync` - Sync heart rate data from Oura

### Reports
- `POST /api/reports/{event_id}/sync-all` - Sync all participants' data
- `GET /api/reports/{event_id}/data` - Get aggregated report data
- `GET /api/reports/{event_id}/pdf` - Download PDF report

### Auth
- `GET /auth/oura/authorize` - Initiate Oura OAuth flow
- `GET /auth/oura/callback` - OAuth callback handler

## Usage Flow

1. **Create an event** via API with start/end times
2. **Get QR code** and display at venue entrance
3. **Participants scan QR** and connect their Oura Ring
4. **After event**, sync data and generate report

## Database Schema

```
events
├── id (UUID)
├── name
├── description
├── location
├── start_time
├── end_time
├── opt_in_code (unique, for QR)
└── created_at

participants
├── id (UUID)
├── event_id (FK)
├── display_name
├── email
├── oura_access_token
├── oura_refresh_token
├── oura_token_expires_at
├── consent_given
└── created_at

heart_rate_data
├── id (UUID)
├── participant_id (FK)
├── timestamp
├── bpm
├── source (oura/apple)
└── created_at
```

## Roadmap

- [ ] Apple Health integration
- [ ] Real-time dashboard
- [ ] Event comparison reports
- [ ] Webhook notifications

## License

MIT
