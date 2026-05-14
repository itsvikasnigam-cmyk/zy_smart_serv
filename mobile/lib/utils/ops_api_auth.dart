import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/ops_api_repository.dart';
import '../state/session_controller.dart';

/// Returns **true** if the error was handled (401 logout or 403 message). Otherwise **false**.
bool handleOpsUnauthorizedAndForbidden(
  BuildContext context,
  Object error, {
  required void Function(String message) onMessage,
}) {
  if (error is OpsApiUnauthorizedException) {
    context.read<SessionController>().logout();
    return true;
  }
  if (error is OpsApiForbiddenException) {
    onMessage(error.userMessage);
    return true;
  }
  return false;
}
