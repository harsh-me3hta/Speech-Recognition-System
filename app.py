from flask import Flask, render_template, request, jsonify
import speech_recognition as sr
import io
import os
from werkzeug.utils import secure_filename
import tempfile
from pydub import AudioSegment
from pydub.utils import which

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize speech recognizer
recognizer = sr.Recognizer()

# Allowed file extensions
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'flac', 'm4a', 'ogg'}

def convert_to_wav(input_path, output_path):
    """Convert audio file to WAV format for speech recognition"""
    try:
        # Load audio file with pydub
        audio = AudioSegment.from_file(input_path)
        
        # Convert to mono and set sample rate to 16kHz (optimal for speech recognition)
        audio = audio.set_channels(1).set_frame_rate(16000)
        
        # Export as WAV
        audio.export(output_path, format="wav")
        return True
    except Exception as e:
        print(f"Error converting audio: {str(e)}")
        return False

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/transcribe_microphone', methods=['POST'])
def transcribe_microphone():
    """Transcribe audio from microphone"""
    try:
        with sr.Microphone() as source:
            print("Adjusting for ambient noise...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            print("Listening...")
            
            # Listen for audio with timeout
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=30)
            
            print("Processing audio...")
            # Use Google's speech recognition
            text = recognizer.recognize_google(audio)
            
            return jsonify({
                'success': True,
                'transcript': text,
                'message': 'Transcription successful'
            })
            
    except sr.RequestError as e:
        return jsonify({
            'success': False,
            'error': f'Could not request results; {str(e)}',
            'message': 'Speech recognition service error'
        })
    except sr.UnknownValueError:
        return jsonify({
            'success': False,
            'error': 'Could not understand audio',
            'message': 'Speech not recognized'
        })
    except sr.WaitTimeoutError:
        return jsonify({
            'success': False,
            'error': 'Listening timeout',
            'message': 'No speech detected within time limit'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Unexpected error: {str(e)}',
            'message': 'An error occurred during transcription'
        })

@app.route('/transcribe_file', methods=['POST'])
def transcribe_file():
    """Transcribe uploaded audio file"""
    try:
        if 'audio' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No audio file provided',
                'message': 'Please select an audio file'
            })
        
        file = request.files['audio']
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected',
                'message': 'Please select an audio file'
            })
        
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': 'Invalid file type',
                'message': f'Supported formats: {", ".join(ALLOWED_EXTENSIONS)}'
            })
        
        # Save uploaded file temporarily
        filename = secure_filename(file.filename)
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, filename)
        file.save(temp_path)
        
        # Create temporary WAV file path
        wav_filename = os.path.splitext(filename)[0] + '_converted.wav'
        wav_path = os.path.join(temp_dir, wav_filename)
        
        try:
            # Convert to WAV format if needed
            file_ext = filename.rsplit('.', 1)[1].lower()
            
            if file_ext == 'wav':
                # If already WAV, use directly
                audio_path = temp_path
            else:
                # Convert to WAV format
                print(f"Converting {file_ext.upper()} to WAV format...")
                if not convert_to_wav(temp_path, wav_path):
                    return jsonify({
                        'success': False,
                        'error': f'Failed to convert {file_ext.upper()} file to WAV format',
                        'message': 'Audio conversion failed'
                    })
                audio_path = wav_path
            
            # Load audio file for speech recognition
            with sr.AudioFile(audio_path) as source:
                print(f"Processing converted audio file...")
                
                # Adjust for ambient noise
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                # Record the audio
                audio = recognizer.record(source)
                
                # Transcribe audio
                print("Transcribing audio...")
                text = recognizer.recognize_google(audio)
                
                return jsonify({
                    'success': True,
                    'transcript': text,
                    'message': f'File "{filename}" transcribed successfully'
                })
                
        finally:
            # Clean up temporary files
            for temp_file in [temp_path, wav_path]:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
            
    except sr.RequestError as e:
        return jsonify({
            'success': False,
            'error': f'Could not request results; {str(e)}',
            'message': 'Speech recognition service error'
        })
    except sr.UnknownValueError:
        return jsonify({
            'success': False,
            'error': 'Could not understand audio in file',
            'message': 'No speech recognized in the audio file'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error processing file: {str(e)}',
            'message': 'An error occurred while processing the file'
        })

@app.route('/check_microphone', methods=['GET'])
def check_microphone():
    """Check if microphone is available"""
    try:
        # Get list of available microphones
        mic_list = sr.Microphone.list_microphone_names()
        
        if not mic_list:
            return jsonify({
                'success': False,
                'error': 'No microphones found',
                'message': 'Please connect a microphone'
            })
        
        return jsonify({
            'success': True,
            'microphones': mic_list,
            'message': f'Found {len(mic_list)} microphone(s)'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error checking microphones: {str(e)}',
            'message': 'Could not access audio devices'
        })

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    print("Starting Speech Recognition Server...")
    print("Make sure you have the following packages installed:")
    print("pip install flask speechrecognition pyaudio pydub")
    print("\nFor audio conversion support:")
    print("- Install FFmpeg: https://ffmpeg.org/download.html")
    print("- Or install via: pip install pydub[mp3]")
    print("\nServer will be available at: http://localhost:5000")
    
    # Check if FFmpeg is available
    if which("ffmpeg") is None:
        print("\nWARNING: FFmpeg not found. MP3/M4A conversion may not work.")
        print("Please install FFmpeg for full audio format support.")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
