"""
apk_static_analyzer.py — manifest-only static analysis of an APK.

Uses androguard's APK class directly (not AnalyzeAPK) because we only need
manifest metadata. This is faster and avoids the full DEX analysis overhead.
Compatible with androguard==3.4.0 on Python 3.10+.
"""

from androguard.core.apk import APK


def analyze_apk(apk_path: str) -> dict:
    """
    Parse the APK manifest and return key metadata.
    No DEX / class analysis performed — instant, no emulator required.
    """
    a = APK(apk_path)
    return {
        "package_name": a.get_package(),
        "main_activity": a.get_main_activity(),
        "all_activities": list(a.get_activities()),
        "permissions": list(a.get_permissions()),
        "app_name": a.get_app_name(),
        "version": a.get_androidversion_name(),
        "target_sdk": str(a.get_effective_target_sdk_version()),
    }
