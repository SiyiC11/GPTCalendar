# 🗓️ GPTCalendar

> AI-powered voice-to-calendar assistant that seamlessly converts natural language into Google Calendar events

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT-412991.svg)](https://openai.com/)
[![Google Calendar](https://img.shields.io/badge/Google-Calendar_API-4285F4.svg)](https://developers.google.com/calendar)

## 📋 Overview

GPTCalendar is an intelligent calendar management system that leverages OpenAI's GPT models for natural language processing and voice recognition, enabling users to create, manage, and organize Google Calendar events through conversational interactions. Simply speak or type your scheduling needs, and GPTCalendar handles the rest.

### ✨ Key Features

- **🎤 Voice Recognition**: Convert spoken language into calendar events effortlessly
- **🤖 Natural Language Processing**: Powered by GPT for understanding complex scheduling requests
- **📅 Google Calendar Integration**: Direct synchronization with Google Calendar API
- **🔒 Secure Credential Management**: Environment-based credential storage (no exposed secrets)
- **☁️ Cloud-Ready Deployment**: Designed for easy deployment on web services with environment variable support
- **⚡ Real-time Event Creation**: Instant calendar updates from voice or text input

## 🎯 Use Cases

- Quick hands-free scheduling while multitasking
- Natural language event creation ("Schedule a meeting with John next Tuesday at 2 PM")
- Voice-activated reminders and task management
- Accessibility tool for users who prefer voice interactions
- Streamlined calendar management for busy professionals

## 🛠️ Technology Stack

- **Backend**: Python 3.8+
- **AI/ML**: OpenAI GPT API (Speech Recognition & NLP)
- **Calendar Service**: Google Calendar API
- **Authentication**: OAuth 2.0
- **Deployment**: Environment variable-based configuration (Render, Heroku, Railway compatible)
- **Security**: Base64-encoded credentials with environment variables

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Google Cloud Platform account with Calendar API enabled
- OpenAI API key
- `client_secret.json` from Google Cloud Console

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/SiyiC11/GPTCalendar.git
   cd GPTCalendar
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Google Calendar API**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable Google Calendar API
   - Create OAuth 2.0 credentials
   - Download `client_secret.json`

4. **Configure environment variables**
   
   Encode your credentials to base64:
   ```bash
   # Linux/Mac
   cat client_secret.json | base64
   
   # Or using Python
   python -c "import base64; print(base64.b64encode(open('client_secret.json','rb').read()).decode())"
   ```
   
   Set the environment variable:
   ```bash
   export GOOGLE_CREDS_B64="<your-base64-encoded-credentials>"
   export OPENAI_API_KEY="<your-openai-api-key>"
   ```

5. **Run the application**
   ```bash
   python main.py
   ```

## 📦 Deployment

### Cloud Deployment (Render, Heroku, Railway)

1. **Navigate to your web service dashboard**
2. **Add environment variables**:
   - `GOOGLE_CREDS_B64`: Base64-encoded `client_secret.json`
   - `OPENAI_API_KEY`: Your OpenAI API key

3. **Deploy** - The service will automatically read credentials and start

### Docker Deployment

```bash
docker build -t gptcalendar .
docker run -e GOOGLE_CREDS_B64="<encoded-creds>" -e OPENAI_API_KEY="<key>" gptcalendar
```

## 💡 How It Works

1. **Voice Input**: User speaks or types a scheduling request
2. **Speech Processing**: OpenAI Whisper converts speech to text (if voice input)
3. **Natural Language Understanding**: GPT analyzes the text to extract:
   - Event title
   - Date and time
   - Duration
   - Attendees (if mentioned)
   - Location (if mentioned)
4. **Calendar Integration**: Formatted event is created in Google Calendar via API
5. **Confirmation**: User receives confirmation of the created event

## 🔐 Security Best Practices

This project implements secure credential management:

- ✅ **No hardcoded secrets** in the repository
- ✅ **Environment variable-based** configuration
- ✅ **Base64 encoding** for credential transmission
- ✅ **OAuth 2.0** for Google Calendar authentication
- ✅ **`.gitignore`** configured to exclude sensitive files

## 📊 Project Architecture

```
GPTCalendar/
├── main.py                 # Application entry point
├── calendar_service.py     # Google Calendar API integration
├── gpt_processor.py        # GPT natural language processing
├── voice_handler.py        # Voice recognition module
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variable template
└── README.md              # Project documentation
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 🐛 Known Issues & Future Enhancements

### Future Roadmap
- [ ] Multi-language support
- [ ] Mobile application (iOS/Android)
- [ ] Calendar event editing and deletion via voice
- [ ] Integration with other calendar services (Outlook, Apple Calendar)
- [ ] Smart scheduling suggestions based on calendar patterns
- [ ] Group meeting time finder

## 👨‍💻 Author

**Stephen Chen**
- GitHub: [@SiyiC11](https://github.com/SiyiC11)
- LinkedIn: www.linkedin.com/in/stephen-chan-6148b0326

## 🙏 Acknowledgments

- OpenAI for GPT and Whisper APIs
- Google Calendar API documentation
- The open-source community

## 📞 Contact

For questions, suggestions, or collaboration opportunities, please reach out through:
- GitHub Issues: [Create an issue](https://github.com/SiyiC11/GPTCalendar/issues)
- Email: siyic46@gmail.com

---

<div align="center">
  <strong>⭐ If you find this project useful, please consider giving it a star! ⭐</strong>
</div>
