import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:speech_to_text/speech_to_text.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:record/record.dart';
import 'package:path_provider/path_provider.dart';

class VoiceAssistantService {
  final SpeechToText _speech = SpeechToText();
  final AudioRecorder _audioRecorder = AudioRecorder();
  final FlutterTts _tts = FlutterTts();
  
  bool _isSpeechInitialized = false;
  bool _isListening = false;
  bool _isSpeaking = false;
  String? _recordingPath;
  String? _lastRecognizedText;
  VoidCallback? _activeOnDone;
  Function(String)? _activeOnError;

  bool get isListening => _isListening;
  bool get isSpeaking => _isSpeaking;

  VoiceAssistantService() {
    _initTts();
  }

  Future<void> _initTts() async {
    try {
      await _tts.setSpeechRate(0.5);
      await _tts.setVolume(1.0);
      await _tts.setPitch(1.0);

      _tts.setStartHandler(() {
        _isSpeaking = true;
        debugPrint('[TTS] Audio received / Playback started');
      });
      _tts.setCompletionHandler(() {
        _isSpeaking = false;
        debugPrint('[TTS] Playback completed');
      });
      _tts.setErrorHandler((msg) {
        _isSpeaking = false;
        debugPrint('[TTS] Playback error: $msg');
      });
    } catch (e) {
      debugPrint('[TTS] Init error: $e');
    }
  }

  Future<bool> initSpeech() async {
    if (_isSpeechInitialized) return true;
    try {
      debugPrint('[VOICE] Initializing speech recognition engine...');
      _isSpeechInitialized = await _speech.initialize(
        onError: (val) {
          debugPrint('[VOICE] Speech error event: ${val.errorMsg}');
          final msg = val.errorMsg.toLowerCase();
          if (!msg.contains('speech_timeout') && !msg.contains('no_match') && !msg.contains('error_busy')) {
            _activeOnError?.call(val.errorMsg);
          }
        },
        onStatus: (val) {
          debugPrint('[VOICE] Speech status change: $val');
        },
      );
      return _isSpeechInitialized;
    } catch (e) {
      debugPrint('[VOICE] Speech init failed: $e');
      return false;
    }
  }

  String _getLocaleId(String languageCode) {
    const localeMap = {
      'hi': 'hi_IN',
      'mr': 'mr_IN',
      'bn': 'bn_IN',
      'te': 'te_IN',
      'ta': 'ta_IN',
      'gu': 'gu_IN',
      'kn': 'kn_IN',
      'ml': 'ml_IN',
      'pa': 'pa_IN',
      'or': 'or_IN',
      'as': 'as_IN',
      'ur': 'ur_IN',
      'sa': 'sa_IN',
      'ne': 'ne_IN',
      'sd': 'sd_IN',
      'kok': 'kok_IN',
      'mai': 'mai_IN',
      'doi': 'doi_IN',
    };
    return localeMap[languageCode] ?? 'en_IN';
  }

  Future<void> startListening({
    required String languageCode,
    required Function(String recognizedText, bool isFinal) onResult,
    required VoidCallback onDone,
    Function(String errorMessage)? onError,
    Future<Map<String, dynamic>> Function(List<int> bytes, String filename)? transcribeApi,
  }) async {
    debugPrint('[VOICE] Microphone button pressed');
    await stopSpeaking();

    _activeOnDone = onDone;
    _activeOnError = onError;
    _lastRecognizedText = null;

    // 1. Start audio file recording to capture raw audio for Groq Whisper
    try {
      if (await _audioRecorder.hasPermission()) {
        final dir = await getTemporaryDirectory();
        _recordingPath = '${dir.path}/voice_query_${DateTime.now().millisecondsSinceEpoch}.m4a';
        await _audioRecorder.start(
          const RecordConfig(encoder: AudioEncoder.aacLc),
          path: _recordingPath!,
        );
        debugPrint('[VOICE] AudioRecorder recording started at $_recordingPath');
      }
    } catch (e) {
      debugPrint('[VOICE] AudioRecorder start warning: $e');
    }

    _isListening = true;
    final targetLocale = _getLocaleId(languageCode);

    // 2. Start real-time speech-to-text listener
    final available = await initSpeech();
    if (available) {
      try {
        await _speech.listen(
          onResult: (result) {
            debugPrint('[VOICE] STT result received: "${result.recognizedWords}" (final: ${result.finalResult})');
            if (result.recognizedWords.isNotEmpty) {
              _lastRecognizedText = result.recognizedWords;
              onResult(result.recognizedWords, result.finalResult);
            }
          },
          listenFor: const Duration(seconds: 30),
          pauseFor: const Duration(seconds: 5),
          partialResults: true,
          localeId: targetLocale,
          cancelOnError: false,
          listenMode: ListenMode.dictation,
        );
      } catch (e) {
        debugPrint('[VOICE] Speech.listen warning: $e');
      }
    }
  }

  Future<void> stopListening({
    Function(String recognizedText, bool isFinal)? onResult,
    Future<Map<String, dynamic>> Function(List<int> bytes, String filename)? transcribeApi,
    String languageCode = 'en',
  }) async {
    debugPrint('[VOICE] Stop requested');
    if (_isListening) {
      try {
        await _speech.stop();
      } catch (e) {
        debugPrint('[VOICE] Error during speech.stop(): $e');
      }
      _isListening = false;
    }

    String? recordedFile = _recordingPath;
    _recordingPath = null;

    if (recordedFile != null) {
      try {
        final path = await _audioRecorder.stop();
        final actualPath = path ?? recordedFile;
        final file = File(actualPath);
        if (await file.exists()) {
          final bytes = await file.readAsBytes();
          debugPrint('[VOICE] Audio recorded: ${bytes.length} bytes');
          if ((_lastRecognizedText == null || _lastRecognizedText!.isEmpty) && transcribeApi != null && bytes.length > 500) {
            debugPrint('[VOICE] Sending audio bytes to Groq Whisper STT endpoint...');
            final resp = await transcribeApi(bytes, 'voice_query.m4a');
            final text = resp['text'] as String?;
            if (text != null && text.isNotEmpty) {
              debugPrint('[VOICE] Groq Whisper transcribed: "$text"');
              onResult?.call(text, true);
            }
          }
        }
      } catch (e) {
        debugPrint('[VOICE] AudioRecorder stop/transcribe warning: $e');
      }
    }

    final callback = _activeOnDone;
    _activeOnDone = null;
    callback?.call();
  }

  Future<void> speak(String text, {required String languageCode}) async {
    try {
      await stopSpeaking();

      final cleanText = text
          .replaceAll(RegExp(r'\[.*?\]\(.*?\)', caseSensitive: false), '')
          .replaceAll(RegExp(r'[*#_~`📌💰📋🔗•]', caseSensitive: false), ' ')
          .replaceAll(RegExp(r'\s+'), ' ')
          .trim();

      if (cleanText.isEmpty) return;

      debugPrint('[TTS] Request sent for text length ${cleanText.length}');

      const ttsMap = {
        'hi': 'hi-IN',
        'mr': 'mr-IN',
        'bn': 'bn-IN',
        'te': 'te-IN',
        'ta': 'ta-IN',
        'gu': 'gu-IN',
        'kn': 'kn-IN',
        'ml': 'ml-IN',
        'pa': 'pa-IN',
        'or': 'or-IN',
        'as': 'as-IN',
        'ur': 'ur-IN',
        'sa': 'sa-IN',
        'ne': 'ne-IN',
        'sd': 'sd_IN',
        'fr': 'fr-FR',
        'es': 'es-ES',
        'de': 'de-DE',
        'ru': 'ru-RU',
        'ja': 'ja-JP',
        'zh': 'zh-CN',
      };
      final ttsLanguage = ttsMap[languageCode] ?? '${languageCode}_IN';
      
      try {
        await _tts.setLanguage(ttsLanguage);
      } catch (_) {
        await _tts.setLanguage('en-IN');
      }

      _isSpeaking = true;
      await _tts.speak(cleanText);
    } catch (e) {
      _isSpeaking = false;
      debugPrint('[TTS] Speak error: $e');
    }
  }

  Future<void> stopSpeaking() async {
    try {
      await _tts.stop();
      _isSpeaking = false;
    } catch (e) {
      debugPrint('TTS stop error: $e');
    }
  }

  Future<void> stop() async => stopSpeaking();
}

final voiceAssistantServiceProvider = Provider<VoiceAssistantService>((ref) {
  return VoiceAssistantService();
});

