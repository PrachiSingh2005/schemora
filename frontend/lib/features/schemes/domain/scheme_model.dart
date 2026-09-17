class SchemeSourceModel {
  final String id;
  final String sourceName;
  final String url;
  final String sourceType;
  final String? lastVerifiedAt;

  SchemeSourceModel({
    required this.id,
    required this.sourceName,
    required this.url,
    required this.sourceType,
    this.lastVerifiedAt,
  });

  factory SchemeSourceModel.fromJson(Map<String, dynamic> json) {
    return SchemeSourceModel(
      id: json['id'] as String,
      sourceName: json['source_name'] as String,
      url: json['url'] as String,
      sourceType: json['source_type'] as String? ?? 'OfficialPortal',
      lastVerifiedAt: json['last_verified_at'] as String?,
    );
  }
}

class SchemeRuleModel {
  final String id;
  final String ruleId;
  final String fieldName;
  final String operator;
  final String expectedValue;
  final String ruleType;
  final String? failureReason;

  SchemeRuleModel({
    required this.id,
    required this.ruleId,
    required this.fieldName,
    required this.operator,
    required this.expectedValue,
    required this.ruleType,
    this.failureReason,
  });

  factory SchemeRuleModel.fromJson(Map<String, dynamic> json) {
    return SchemeRuleModel(
      id: json['id'] as String,
      ruleId: json['rule_id'] as String,
      fieldName: json['field_name'] as String,
      operator: json['operator'] as String,
      expectedValue: json['expected_value'] as String,
      ruleType: json['rule_type'] as String? ?? 'mandatory',
      failureReason: json['failure_reason'] as String?,
    );
  }
}

class SchemeModel {
  final String id;
  final String slug;
  final String title;
  final String shortDescription;
  final String? detailedDescription;
  final String provider;
  final String jurisdiction;
  final String? state;
  final String benefitType;
  final String benefitSummary;
  final String? beneficiaries;
  final String implementationStatus;
  final bool isPublished;
  final String? applicationDeadline;
  final String? officialSchemeUrl;
  final String? applicationUrl;
  final String? officialPortalUrl;
  final String? bestApplyUrl;
  final String? bestInfoUrl;
  final List<SchemeRuleModel> rules;
  final List<SchemeSourceModel> sources;

  SchemeModel({
    required this.id,
    required this.slug,
    required this.title,
    required this.shortDescription,
    this.detailedDescription,
    required this.provider,
    required this.jurisdiction,
    this.state,
    required this.benefitType,
    required this.benefitSummary,
    this.beneficiaries,
    required this.implementationStatus,
    required this.isPublished,
    this.applicationDeadline,
    this.officialSchemeUrl,
    this.applicationUrl,
    this.officialPortalUrl,
    this.bestApplyUrl,
    this.bestInfoUrl,
    this.rules = const [],
    this.sources = const [],
  });

  factory SchemeModel.fromJson(Map<String, dynamic> json) {
    return SchemeModel(
      id: json['id'] as String,
      slug: json['slug'] as String? ?? '',
      title: json['title'] as String,
      shortDescription: json['short_description'] as String? ?? '',
      detailedDescription: json['detailed_description'] as String?,
      provider: json['provider'] as String? ?? 'Government',
      jurisdiction: json['jurisdiction'] as String? ?? 'Central',
      state: json['state'] as String?,
      benefitType: json['benefit_type'] as String? ?? 'Financial',
      benefitSummary: json['benefit_summary'] as String? ?? 'Scholarship',
      beneficiaries: json['beneficiaries'] as String?,
      implementationStatus: json['implementation_status'] as String? ?? 'Implemented',
      isPublished: json['is_published'] as bool? ?? true,
      applicationDeadline: json['application_deadline'] as String?,
      officialSchemeUrl: json['official_scheme_url'] as String?,
      applicationUrl: json['application_url'] as String?,
      officialPortalUrl: json['official_portal_url'] as String?,
      bestApplyUrl: json['best_apply_url'] as String?,
      bestInfoUrl: json['best_info_url'] as String?,
      rules: (json['rules'] as List<dynamic>?)
              ?.map((r) => SchemeRuleModel.fromJson(r as Map<String, dynamic>))
              .toList() ??
          [],
      sources: (json['sources'] as List<dynamic>?)
              ?.map((s) => SchemeSourceModel.fromJson(s as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }
}

class RecommendationItemModel {
  final String schemeId;
  final String schemeTitle;
  final String provider;
  final String jurisdiction;
  final String benefitSummary;
  final String status; // RuleMatched, NeedsInformation, NotMatched
  final double confidenceScore;
  final int matchedRulesCount;
  final int unresolvedRulesCount;
  final int failedRulesCount;
  final List<String> unresolvedFields;
  final String matchType; // LIKELY_MATCH, POTENTIAL_MATCH, REQUIRES_VERIFICATION
  final List<String> matchReasons;
  final String relevanceExplanation;
  final String? eligibilitySummary;
  final String? officialSchemeUrl;
  final String? applicationUrl;
  final String? bestActionUrl;

  const RecommendationItemModel({
    required this.schemeId,
    required this.schemeTitle,
    required this.provider,
    required this.jurisdiction,
    required this.benefitSummary,
    required this.status,
    required this.confidenceScore,
    required this.matchedRulesCount,
    required this.unresolvedRulesCount,
    required this.failedRulesCount,
    required this.unresolvedFields,
    this.matchType = 'LIKELY_MATCH',
    this.matchReasons = const [],
    this.relevanceExplanation = '',
    this.eligibilitySummary,
    this.officialSchemeUrl,
    this.applicationUrl,
    this.bestActionUrl,
  });

  factory RecommendationItemModel.fromJson(Map<String, dynamic> json) {
    final mType = json['match_type'] as String? ?? 
      (json['status'] == 'RuleMatched' ? 'LIKELY_MATCH' : 'POTENTIAL_MATCH');
    final mReasons = (json['match_reasons'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [];

    return RecommendationItemModel(
      schemeId: json['scheme_id'] as String? ?? json['id'] as String? ?? '',
      schemeTitle: json['scheme_name'] as String? ?? json['scheme_title'] as String? ?? '',
      provider: json['provider'] as String? ?? 'Government',
      jurisdiction: json['jurisdiction'] as String? ?? 'Central',
      benefitSummary: json['benefits'] as String? ?? json['benefit_summary'] as String? ?? '',
      status: json['status'] as String? ?? (mType == 'LIKELY_MATCH' ? 'RuleMatched' : 'NeedsInformation'),
      confidenceScore: (json['score'] as num?)?.toDouble() ?? (json['confidence_score'] as num?)?.toDouble() ?? 0.85,
      matchedRulesCount: json['matched_rules_count'] as int? ?? mReasons.length,
      unresolvedRulesCount: json['unresolved_rules_count'] as int? ?? 0,
      failedRulesCount: json['failed_rules_count'] as int? ?? 0,
      unresolvedFields: (json['unresolved_fields'] as List<dynamic>?)?.map((e) => e as String).toList() ?? [],
      matchType: mType,
      matchReasons: mReasons,
      relevanceExplanation: json['relevance_explanation'] as String? ?? json['why_relevant'] as String? ?? '',
      eligibilitySummary: json['eligibility'] as String?,
      officialSchemeUrl: json['official_scheme_url'] as String?,
      applicationUrl: json['application_url'] as String?,
      bestActionUrl: json['best_action_url'] as String? ?? json['application_url'] as String? ?? json['official_scheme_url'] as String?,
    );
  }
}

