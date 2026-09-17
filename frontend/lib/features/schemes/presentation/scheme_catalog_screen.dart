import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:schemora_frontend/core/theme/app_theme.dart';
import 'package:schemora_frontend/core/widgets/common_states.dart';
import 'package:schemora_frontend/core/widgets/dashboard_button.dart';
import 'package:schemora_frontend/features/schemes/data/scheme_repository.dart';
import 'package:schemora_frontend/features/schemes/domain/scheme_model.dart';
import 'package:schemora_frontend/features/saved_schemes/data/saved_scheme_repository.dart';
import 'package:schemora_frontend/core/widgets/scheme_card.dart';

class SchemeCatalogScreen extends ConsumerStatefulWidget {
  const SchemeCatalogScreen({super.key});

  @override
  ConsumerState<SchemeCatalogScreen> createState() => _SchemeCatalogScreenState();
}

class _SchemeCatalogScreenState extends ConsumerState<SchemeCatalogScreen> {
  final _searchController = TextEditingController();
  final _scrollController = ScrollController();

  String _selectedJurisdiction = '';
  String _selectedCategory = '';
  bool _forceRefresh = false;

  final List<String> _categories = const [
    'All Schemes',
    'Central',
    'State',
    'Maharashtra',
    'Agriculture',
    'Education',
    'Scholarship',
    'Women',
    'Health',
    'Housing',
    'Pension',
    'Employment',
  ];

  @override
  void dispose() {
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToTop() {
    if (_scrollController.hasClients) {
      _scrollController.animateTo(
        0,
        duration: const Duration(milliseconds: 500),
        curve: Curves.easeOutCubic,
      );
    }
  }

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 500),
        curve: Curves.easeOutCubic,
      );
    }
  }

  void _onChipSelected(String cat) {
    setState(() {
      if (cat == 'All Schemes') {
        _selectedJurisdiction = '';
        _selectedCategory = '';
      } else if (cat == 'Central') {
        _selectedJurisdiction = 'Central';
        _selectedCategory = '';
      } else if (cat == 'State') {
        _selectedJurisdiction = 'State';
        _selectedCategory = '';
      } else {
        _selectedJurisdiction = '';
        _selectedCategory = cat;
      }
    });
  }

  bool _isChipSelected(String cat) {
    if (cat == 'All Schemes') {
      return _selectedJurisdiction == '' && _selectedCategory == '';
    } else if (cat == 'Central') {
      return _selectedJurisdiction == 'Central';
    } else if (cat == 'State') {
      return _selectedJurisdiction == 'State';
    } else {
      return _selectedCategory == cat;
    }
  }

  Future<void> _refreshCatalog() async {
    setState(() {
      _forceRefresh = true;
    });
  }

  @override
  Widget build(BuildContext context) {
    final repo = ref.watch(schemeRepositoryProvider);
    final savedIds = ref.watch(savedSchemeIdsProvider).value ?? {};

    final currentForceRefresh = _forceRefresh;
    if (_forceRefresh) {
      // reset flag after triggering future
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) setState(() => _forceRefresh = false);
      });
    }

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded),
          tooltip: 'Go Back',
          onPressed: () => context.canPop() ? context.pop() : context.go('/dashboard'),
        ),
        title: const Text('All Government Schemes'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded, color: AppTheme.primaryBlue),
            tooltip: 'Reload All Schemes',
            onPressed: _refreshCatalog,
          ),
          IconButton(
            icon: const Icon(Icons.bookmark_rounded, color: AppTheme.primaryBlue),
            tooltip: 'Saved Schemes',
            onPressed: () => context.push('/saved-schemes'),
          ),
          const DashboardButton(),
          IconButton(
            icon: const Icon(Icons.star_rounded, color: AppTheme.warningOrange),
            tooltip: 'Top Recommendations',
            onPressed: () => context.push('/recommendations'),
          ),
        ],
      ),
      floatingActionButtonLocation: FloatingActionButtonLocation.endFloat,
      floatingActionButton: Container(
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(
          color: AppTheme.primaryNavy,
          borderRadius: BorderRadius.circular(30),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withAlpha(40),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              IconButton(
                icon: const Icon(Icons.arrow_upward_rounded, color: Colors.white, size: 20),
                tooltip: 'Scroll to Top',
                onPressed: _scrollToTop,
              ),
              const Text(
                'SCROLL',
                style: TextStyle(
                  color: Colors.white70,
                  fontSize: 10,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0.8,
                ),
              ),
              IconButton(
                icon: const Icon(Icons.arrow_downward_rounded, color: Colors.white, size: 20),
                tooltip: 'Scroll to Bottom',
                onPressed: _scrollToBottom,
              ),
            ],
          ),
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  TextField(
                    controller: _searchController,
                    style: const TextStyle(fontSize: 14, color: AppTheme.primaryNavy),
                    decoration: InputDecoration(
                      hintText: 'Search schemes by keyword, ministry or benefit...',
                      prefixIcon: const Icon(Icons.search_rounded, color: AppTheme.primaryBlue),
                      suffixIcon: _searchController.text.isNotEmpty
                          ? IconButton(
                              icon: const Icon(Icons.clear_rounded, size: 18, color: Color(0xFF94A3B8)),
                              onPressed: () {
                                _searchController.clear();
                                setState(() {});
                              },
                            )
                          : null,
                      filled: true,
                      fillColor: Colors.white,
                      contentPadding: const EdgeInsets.symmetric(vertical: 14, horizontal: 16),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(14),
                        borderSide: const BorderSide(color: Color(0xFFE2E8F0)),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(14),
                        borderSide: const BorderSide(color: AppTheme.primaryBlue, width: 1.5),
                      ),
                    ),
                    onChanged: (val) => setState(() {}),
                  ),
                  const SizedBox(height: 12),
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: _categories.map((cat) {
                        final selected = _isChipSelected(cat);
                        return Padding(
                          padding: const EdgeInsets.only(right: 8.0),
                          child: FilterChip(
                            label: Text(cat),
                            selected: selected,
                            selectedColor: AppTheme.primaryBlue.withAlpha(30),
                            checkmarkColor: AppTheme.primaryBlue,
                            labelStyle: TextStyle(
                              color: selected ? AppTheme.primaryBlue : AppTheme.primaryNavy,
                              fontWeight: selected ? FontWeight.w800 : FontWeight.w500,
                              fontSize: 12.5,
                            ),
                            onSelected: (_) => _onChipSelected(cat),
                          ),
                        );
                      }).toList(),
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: FutureBuilder<List<SchemeModel>>(
                future: repo.getSchemes(
                  query: _searchController.text,
                  jurisdiction: _selectedJurisdiction,
                  category: _selectedCategory,
                  forceRefresh: currentForceRefresh,
                ),
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const LoadingStateWidget(message: 'Loading schemes catalog...');
                  }
                  if (snapshot.hasError) {
                    return ErrorStateWidget(
                      message: 'Unable to load schemes. Please try again.',
                      onRetry: _refreshCatalog,
                    );
                  }
                  final schemes = snapshot.data ?? [];
                  if (schemes.isEmpty) {
                    return EmptyStateWidget(
                      title: 'No Schemes Found',
                      description: 'No schemes match your current search parameters.',
                      icon: Icons.search_off_rounded,
                      actionLabel: 'Reset Search & Filters',
                      onAction: () {
                        _searchController.clear();
                        setState(() {
                          _selectedJurisdiction = '';
                          _selectedCategory = '';
                        });
                      },
                    );
                  }
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 6.0),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                              decoration: BoxDecoration(
                                color: AppTheme.primaryBlue.withAlpha(15),
                                borderRadius: BorderRadius.circular(10),
                                border: Border.all(color: AppTheme.primaryBlue.withAlpha(30)),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  const Icon(Icons.apps_rounded, size: 16, color: AppTheme.primaryBlue),
                                  const SizedBox(width: 6),
                                  Text(
                                    '${schemes.length} schemes available',
                                    style: const TextStyle(
                                      fontSize: 12,
                                      fontWeight: FontWeight.w800,
                                      color: AppTheme.primaryBlue,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            Row(
                              children: [
                                InkWell(
                                  onTap: _scrollToTop,
                                  borderRadius: BorderRadius.circular(6),
                                  child: Padding(
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    child: Row(
                                      children: const [
                                        Icon(Icons.arrow_upward_rounded, size: 13, color: AppTheme.primaryBlue),
                                        SizedBox(width: 2),
                                        Text('Top', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppTheme.primaryBlue)),
                                      ],
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 8),
                                InkWell(
                                  onTap: _scrollToBottom,
                                  borderRadius: BorderRadius.circular(6),
                                  child: Padding(
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    child: Row(
                                      children: const [
                                        Icon(Icons.arrow_downward_rounded, size: 13, color: AppTheme.primaryBlue),
                                        SizedBox(width: 2),
                                        Text('Bottom', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: AppTheme.primaryBlue)),
                                      ],
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                      Expanded(
                        child: RefreshIndicator(
                          onRefresh: () async {
                            _refreshCatalog();
                          },
                          child: Scrollbar(
                            controller: _scrollController,
                            thumbVisibility: true,
                            trackVisibility: true,
                            thickness: 7.0,
                            radius: const Radius.circular(8.0),
                            child: ListView.builder(
                              controller: _scrollController,
                              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                              itemCount: schemes.length,
                              itemBuilder: (context, index) {
                                final scheme = schemes[index];
                                final isSaved = savedIds.contains(scheme.id);

                                return SchemeCard(
                                  scheme: scheme,
                                  isSaved: isSaved,
                                  onTap: () => context.push('/catalog/${scheme.id}'),
                                  onBookmarkTap: () async {
                                    try {
                                      final nowSaved = await ref
                                          .read(savedSchemeIdsProvider.notifier)
                                          .toggleSave(scheme.id);
                                      if (context.mounted) {
                                        ScaffoldMessenger.of(context).showSnackBar(
                                          SnackBar(
                                            content: Text(
                                              nowSaved
                                                  ? 'Scheme saved to My Saved Schemes!'
                                                  : 'Scheme removed from Saved Schemes.',
                                            ),
                                            action: SnackBarAction(
                                              label: 'View All',
                                              onPressed: () => context.push('/saved-schemes'),
                                            ),
                                          ),
                                        );
                                      }
                                    } catch (e) {
                                      if (context.mounted) {
                                        ScaffoldMessenger.of(context).showSnackBar(
                                          SnackBar(content: Text('Failed to update bookmark: $e')),
                                        );
                                      }
                                    }
                                  },
                                );
                              },
                            ),
                          ),
                        ),
                      ),
                    ],
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
