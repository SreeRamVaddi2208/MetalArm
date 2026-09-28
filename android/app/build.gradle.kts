plugins { id("com.android.application") }

// The host is a build property (gradle.properties, overridable with -P) rather
// than a literal: the same source has to produce a shell for a staging origin
// and for production, and a hardcoded domain is how those drift apart.
val metalarmHost: String = (project.findProperty("metalarmHost") as String?) ?: "metalarm.example.com"

android {
    namespace = "app.metalarm.twa"
    compileSdk = 35

    defaultConfig {
        applicationId = "app.metalarm.twa"
        minSdk = 26          // Chrome's TWA support; below this it is a tab
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"

        // Read by AndroidManifest.xml through manifestPlaceholders.
        manifestPlaceholders["hostName"] = metalarmHost
        manifestPlaceholders["defaultUrl"] = "https://$metalarmHost/dashboard/"
        manifestPlaceholders["launcherName"] = "MetalArm"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            // Signing is deliberately NOT configured here: the keystore must
            // not live in the repository. Configure it in Android Studio, or
            // pass it on the command line when building for Play.
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    // Google's own TWA helper: it launches the Custom Tab in trusted mode and
    // falls back to a normal Custom Tab where the device cannot verify.
    implementation("com.google.androidbrowserhelper:androidbrowserhelper:2.5.0")
}
