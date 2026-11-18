import java.net.URL
import java.nio.file.Files
import java.nio.file.StandardCopyOption

plugins {
    kotlin("android")
    kotlin("kapt")
    id("com.android.application")
}

dependencies {
    compileOnly(project(":hideapi"))

    implementation(project(":core"))
    implementation(project(":service"))
    implementation(project(":design"))
    implementation(project(":common"))

    implementation(libs.kotlin.coroutine)
    implementation(libs.androidx.core)
    implementation(libs.androidx.activity)
    implementation(libs.androidx.fragment)
    implementation(libs.androidx.appcompat)
    implementation(libs.androidx.coordinator)
    implementation(libs.androidx.recyclerview)
    implementation(libs.google.material)
    implementation(libs.quickie.bundled)
    implementation(libs.androidx.activity.ktx)
}

tasks.getByName("clean", type = Delete::class) {
    delete(file("release"))
}

val geoFilesDownloadDir = file("src/main/assets")
val geoFiles = mapOf(
    "geoip.metadb" to "geoip.metadb",
    "geosite.dat" to "geosite.dat",
    "GeoLite2-ASN.mmdb" to "ASN.mmdb",
    "BundleMRS.7z" to "BundleMRS.7z",
)

val downloadGeoFiles = tasks.register("downloadGeoFiles") {
    doLast {
        geoFilesDownloadDir.mkdirs()
        geoFiles.forEach { (remoteName, localName) ->
            val url = URL("https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/$remoteName")
            val target = geoFilesDownloadDir.resolve(localName).toPath()
            val pending = Files.createTempFile(temporaryDir.toPath(), localName, ".part")
            try {
                url.openStream().use { input ->
                    Files.copy(input, pending, StandardCopyOption.REPLACE_EXISTING)
                }
                Files.move(pending, target, StandardCopyOption.REPLACE_EXISTING)
            } finally {
                Files.deleteIfExists(pending)
            }
        }
    }
}

tasks.matching { it.name.startsWith("merge") && it.name.endsWith("Assets") }.configureEach {
    dependsOn(downloadGeoFiles)
}

tasks.named<Delete>("clean") {
    delete(geoFiles.values.map { geoFilesDownloadDir.resolve(it) })
}
