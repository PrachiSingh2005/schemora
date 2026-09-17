import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:schemora_frontend/core/network/api_client.dart';

abstract class AIRepository {
  Future<Map<String, dynamic>> askAssistant(String question, {String? schemeId, String language = 'en'});
  Future<Map<String, dynamic>> transcribeAudio(List<int> audioBytes, String filename, {String? language});
  Future<List<int>> fetchAudioStream(String text, {String language = 'en'});
}

class AIRepositoryImpl implements AIRepository {
  final Dio _dio;

  AIRepositoryImpl(this._dio);

  @override
  Future<Map<String, dynamic>> askAssistant(String question, {String? schemeId, String language = 'en'}) async {
    final reqBody = {
      'question': question,
      if (schemeId != null) 'scheme_id': schemeId,
      'language': language,
    };

    debugPrint('[AI REPO] Sending chat request to /ai/chat');
    final response = await _dio.post(
      '/ai/chat',
      data: reqBody,
    );
    final dynamic raw = response.data;
    final Map<String, dynamic> map = raw is String ? jsonDecode(raw) as Map<String, dynamic> : (raw as Map<String, dynamic>);
    return map['data'] as Map<String, dynamic>;
  }

  @override
  Future<Map<String, dynamic>> transcribeAudio(List<int> audioBytes, String filename, {String? language}) async {
    final formDataMap = {
      'file': MultipartFile.fromBytes(audioBytes, filename: filename),
      if (language != null) 'language': language,
    };

    debugPrint('[AI REPO] Sending STT request to /ai/speech-to-text');
    final response = await _dio.post(
      '/ai/speech-to-text',
      data: FormData.fromMap(formDataMap),
    );
    final dynamic raw = response.data;
    final Map<String, dynamic> map = raw is String ? jsonDecode(raw) as Map<String, dynamic> : (raw as Map<String, dynamic>);
    return map['data'] as Map<String, dynamic>;
  }

  @override
  Future<List<int>> fetchAudioStream(String text, {String language = 'en'}) async {
    final response = await _dio.post(
      '/ai/text-to-speech',
      data: {
        'text': text,
        'language': language,
      },
      options: Options(responseType: ResponseType.bytes),
    );
    return response.data as List<int>;
  }
}

final aiRepositoryProvider = Provider<AIRepository>((ref) {
  final dio = ref.watch(dioProvider);
  return AIRepositoryImpl(dio);
});


