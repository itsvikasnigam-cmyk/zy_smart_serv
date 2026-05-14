import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:markdown/markdown.dart' as md;

/// Markdown preview without raw HTML inline syntax (reduces XSS surface vs untrusted SOP bodies).
///
/// For full sanitization of rich HTML-in-markdown, **Stem** should add server-side normalization;
/// here we use **CommonMark-only** extensions (no inline HTML).
class SafeMarkdownBody extends StatelessWidget {
  const SafeMarkdownBody({super.key, required this.data});

  final String data;

  @override
  Widget build(BuildContext context) {
    return MarkdownBody(
      data: data,
      selectable: true,
      extensionSet: md.ExtensionSet.commonMark,
    );
  }
}
