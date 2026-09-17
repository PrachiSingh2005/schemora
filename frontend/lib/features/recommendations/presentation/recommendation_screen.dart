import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:schemora_frontend/core/theme/app_theme.dart';
import 'package:schemora_frontend/core/utils/url_launcher_helper.dart';
import 'package:schemora_frontend/core/widgets/common_states.dart';
import 'package:schemora_frontend/core/widgets/dashboard_button.dart';
import 'package:schemora_frontend/core/widgets/scheme_image_helper.dart';
import 'package:schemora_frontend/features/schemes/data/scheme_repository.dart';
import 'package:schemora_frontend/features/schemes/domain/scheme_model.dart';
import 'package:schemora_frontend/features/profile/domain/profile_type_provider.dart';

class RecommendationScreen extends ConsumerWidget {
  const RecommendationScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final top3Async = ref.watch(top3RecommendationsProvider);
    final profileType = ref.watch(selectedProfileTypeProvider);

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded),
          tooltip: 'Go Back',
          onPressed: () => context.canPop() ? context.pop() : context.go('/dashboard'),
        ),
        title: Text('✨ Recommended Schemes (${profileType.displayName})'),
        centerTitle: true,
        actions: [
          const DashboardButton(),
          IconButton(
            icon: const Icon(Icons.tune_rounded),
            tooltip: 'Update Profile',
            onPressed: () => context.go('/profile-type'),
          ),
          IconButton(
            icon: const Icon(Icons.grid_view_rounded),
            tooltip: 'Explore Catalog',
            onPressed: () => context.push('/catalog'),
          ),
        ],
      ),
      body: SafeArea(
        child: top3Async.when(
          loading: () => const LoadingStateWidget(message: 'Finding personalized schemes for you...'),
          error: (err, stack) => ErrorStateWidget(
            message: 'Unable to load recommendations. Please try again.',
            onRetry: () => ref.invalidate(top3RecommendationsProvider),
          ),
          data: (items) {
            if (items.isEmpty) {
              return Center(
                child: Padding(
                  padding: const EdgeInsets.all(24.0),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.search_off_rounded, size: 64, color: Colors.grey),
                      const SizedBox(height: 16),
                      const Text(
                        "I couldn't find reliable scheme matches for your current profile.",
                        textAlign: TextAlign.center,
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppTheme.primaryNavy),
                      ),
                      const SizedBox(height: 24),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          ElevatedButton.icon(
                            onPressed: () => context.go('/profile-type'),
                            icon: const Icon(Icons.edit_note_rounded),
                            label: const Text('Update Profile'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppTheme.primaryBlue,
                              foregroundColor: Colors.white,
                            ),
                          ),
                          const SizedBox(width: 12),
                          OutlinedButton.icon(
                            onPressed: () => context.push('/catalog'),
                            icon: const Icon(Icons.grid_view_rounded),
                            label: const Text('Explore All Schemes'),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              );
            }

            return ListView(
              padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 16.0),
              children: [
                // Header Card
                Container(
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(20),
                    gradient: const LinearGradient(
                      colors: [Color(0xFF0F172A), Color(0xFF1E3A8A), Color(0xFF2563EB)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: AppTheme.primaryNavy.withAlpha(50),
                        blurRadius: 16,
                        offset: const Offset(0, 6),
                      ),
                    ],
                  ),
                  child: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.white.withAlpha(40),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(Icons.auto_awesome_rounded, color: Color(0xFFFBBF24), size: 28),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              '✨ Recommended Schemes For You',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 18,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              'Based on your profile • Tailored government benefits matched deterministically.',
                              style: TextStyle(color: Colors.white.withAlpha(210), fontSize: 12),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 20),

                ...items.asMap().entries.map((entry) {
                  final item = entry.value;
                  return _RecommendationCard(item: item);
                }),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _RecommendationCard extends StatelessWidget {
  final RecommendationItemModel item;

  const _RecommendationCard({required this.item});

  Color _getMatchBadgeColor() {
    switch (item.matchType.toUpperCase()) {
      case 'LIKELY_MATCH':
        return const Color(0xFF10B981); // Emerald Green
      case 'POTENTIAL_MATCH':
        return const Color(0xFFF59E0B); // Amber
      case 'REQUIRES_VERIFICATION':
      default:
        return const Color(0xFF3B82F6); // Blue
    }
  }

  String _getMatchBadgeText() {
    switch (item.matchType.toUpperCase()) {
      case 'LIKELY_MATCH':
        return 'LIKELY MATCH';
      case 'POTENTIAL_MATCH':
        return 'POTENTIAL MATCH';
      case 'REQUIRES_VERIFICATION':
      default:
        return 'REQUIRES VERIFICATION';
    }
  }

  @override
  Widget build(BuildContext context) {
    final badgeColor = _getMatchBadgeColor();
    final badgeText = _getMatchBadgeText();
    final percent = (item.confidenceScore * 100).toInt();

    return Container(
      margin: const EdgeInsets.only(bottom: 20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.grey.shade200),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withAlpha(8),
            blurRadius: 14,
            offset: const Offset(0, 4),
          )
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Thumbnail Image & Badges Banner
            SizedBox(
              height: 110,
              width: double.infinity,
              child: Stack(
                fit: StackFit.expand,
                children: [
                  Image.asset(
                    SchemeImageHelper.getSchemeImage(title: item.schemeTitle),
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => const SizedBox(),
                  ),
                  Container(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [
                          Colors.black.withAlpha(170),
                          Colors.black.withAlpha(50),
                          Colors.transparent,
                        ],
                        begin: Alignment.bottomCenter,
                        end: Alignment.topCenter,
                      ),
                    ),
                  ),
                  Positioned(
                    top: 12,
                    left: 12,
                    right: 12,
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: badgeColor,
                            borderRadius: BorderRadius.circular(10),
                            boxShadow: [
                              BoxShadow(
                                color: badgeColor.withAlpha(90),
                                blurRadius: 4,
                              )
                            ],
                          ),
                          child: Text(
                            badgeText,
                            style: const TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w800,
                              color: Colors.white,
                              letterSpacing: 0.5,
                            ),
                          ),
                        ),
                        const Spacer(),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: Colors.black.withAlpha(160),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text(
                            '$percent% Match',
                            style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 12, color: Colors.white),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),

            Padding(
              padding: const EdgeInsets.all(18.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Scheme Title
                  Text(
                    item.schemeTitle,
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: AppTheme.primaryNavy),
                  ),

                  // Match Reason Tags
                  if (item.matchReasons.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 6,
                      runSpacing: 4,
                      children: item.matchReasons.map((reason) {
                        return Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: AppTheme.primaryBlue.withAlpha(15),
                            borderRadius: BorderRadius.circular(6),
                            border: Border.all(color: AppTheme.primaryBlue.withAlpha(35)),
                          ),
                          child: Text(
                            reason,
                            style: const TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                              color: AppTheme.primaryBlue,
                            ),
                          ),
                        );
                      }).toList(),
                    ),
                  ],

                  // Grounded Why Relevant Block
                  if (item.relevanceExplanation.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: const Color(0xFFEFF6FF),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: const Color(0xFFBFDBFE)),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Row(
                            children: [
                              Icon(Icons.info_outline_rounded, size: 14, color: AppTheme.primaryBlue),
                              SizedBox(width: 6),
                              Text(
                                'Why this is relevant:',
                                style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: AppTheme.primaryBlue),
                              ),
                            ],
                          ),
                          const SizedBox(height: 4),
                          Text(
                            item.relevanceExplanation,
                            style: const TextStyle(fontSize: 12, color: Color(0xFF1E3A8A), height: 1.4),
                          ),
                        ],
                      ),
                    ),
                  ],

                  // Benefits Section
                  if (item.benefitSummary.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    RichText(
                      text: TextSpan(
                        children: [
                          const TextSpan(
                            text: 'Benefits: ',
                            style: TextStyle(fontWeight: FontWeight.bold, color: AppTheme.primaryNavy, fontSize: 13),
                          ),
                          TextSpan(
                            text: item.benefitSummary,
                            style: TextStyle(color: Colors.grey.shade700, fontSize: 13, height: 1.4),
                          ),
                        ],
                      ),
                    ),
                  ],

                  // Eligibility Summary
                  if (item.eligibilitySummary != null && item.eligibilitySummary!.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    RichText(
                      text: TextSpan(
                        children: [
                          const TextSpan(
                            text: 'Eligibility: ',
                            style: TextStyle(fontWeight: FontWeight.bold, color: AppTheme.primaryNavy, fontSize: 13),
                          ),
                          TextSpan(
                            text: item.eligibilitySummary,
                            style: TextStyle(color: Colors.grey.shade700, fontSize: 13, height: 1.4),
                          ),
                        ],
                      ),
                    ),
                  ],

                  const SizedBox(height: 16),
                  const Divider(height: 1),
                  const SizedBox(height: 14),

                  // Action Buttons Row: View Details & Apply
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () => context.push('/catalog/${item.schemeId}'),
                          icon: const Icon(Icons.info_outline_rounded, size: 16),
                          label: const Text('View Details'),
                          style: OutlinedButton.styleFrom(
                            foregroundColor: AppTheme.primaryNavy,
                            side: const BorderSide(color: Color(0xFFCBD5E1)),
                            padding: const EdgeInsets.symmetric(vertical: 10),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: ElevatedButton.icon(
                          onPressed: () => _handleApplyAction(context),
                          icon: const Icon(Icons.open_in_new_rounded, size: 16),
                          label: const Text('Apply / Official'),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppTheme.primaryBlue,
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(vertical: 10),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _handleApplyAction(BuildContext context) {
    final targetUrl = item.bestActionUrl ?? item.applicationUrl ?? item.officialSchemeUrl;
    if (targetUrl == null || targetUrl.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('An official application link is not currently available.'),
          behavior: SnackBarBehavior.floating,
        ),
      );
    } else {
      UrlLauncherHelper.openUrl(context, targetUrl);
    }
  }
}
