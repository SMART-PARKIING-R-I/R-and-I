SmartParking - Kotlin / Jetpack Compose (gate-screen flow)

1. Android Studio: New Project > Empty Activity (Compose), name SmartParking,
   package com.example.smartparking  (if yours differs, change line 1 of the 5 .kt files).
2. Copy the contents of app/src/main/ from this zip over your project's app/src/main/
   (overwrites MainActivity.kt; adds Api.kt, ParkingViewModel.kt, Screens.kt, RouteMap.kt
   and res/drawable-nodpi/lot_a.jpg).
3. In app/src/main/AndroidManifest.xml add, above <application ...>:
       <uses-permission android:name="android.permission.INTERNET" />
   and inside the <application ...> tag add:
       android:usesCleartextTraffic="true"
4. Api.kt: BASE_URL = "http://10.0.2.2:5000" works for the emulator. For a real phone use
   your PC's Wi-Fi IP, e.g. "http://192.168.1.20:5000" (same Wi-Fi as the PC).
5. PC (project park folder):  python seed_app.py   then   python backend.py
   fake occupancy:           python simulate.py     (or: python simulate.py --loop)
6. Run the app (Shift+F10).
