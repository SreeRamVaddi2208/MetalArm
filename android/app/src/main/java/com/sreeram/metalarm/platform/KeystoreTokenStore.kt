// The signed-in tokens, encrypted with a key that never leaves the Android
// Keystore - the twin of the iOS Keychain store. The ciphertext lives in a
// private SharedPreferences file and is excluded from backups (allowBackup is
// false in the manifest).

package com.sreeram.metalarm.platform

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import com.sreeram.metalarm.api.MetalArmJson
import com.sreeram.metalarm.api.TokenPair
import com.sreeram.metalarm.api.TokenStore
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class KeystoreTokenStore(context: Context) : TokenStore {
    private val prefs = context.getSharedPreferences("metalarm.tokens", Context.MODE_PRIVATE)
    @Volatile private var cached: TokenPair? = null
    @Volatile private var loaded = false

    override var tokens: TokenPair?
        get() {
            if (!loaded) {
                cached = runCatching { read() }.getOrNull()
                loaded = true
            }
            return cached
        }
        set(value) {
            cached = value
            loaded = true
            if (value == null) {
                prefs.edit().remove(KEY).apply()
            } else {
                prefs.edit().putString(KEY, encrypt(MetalArmJson.encodeToString(TokenPair.serializer(), value))).apply()
            }
        }

    private fun read(): TokenPair? {
        val stored = prefs.getString(KEY, null) ?: return null
        return MetalArmJson.decodeFromString(TokenPair.serializer(), decrypt(stored))
    }

    private fun key(): SecretKey {
        val keyStore = KeyStore.getInstance(KEYSTORE).apply { load(null) }
        (keyStore.getKey(ALIAS, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE)
        generator.init(
            KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build(),
        )
        return generator.generateKey()
    }

    private fun encrypt(plain: String): String {
        val cipher = Cipher.getInstance(TRANSFORMATION).apply { init(Cipher.ENCRYPT_MODE, key()) }
        val sealed = cipher.iv + cipher.doFinal(plain.toByteArray())
        return Base64.encodeToString(sealed, Base64.NO_WRAP)
    }

    private fun decrypt(stored: String): String {
        val sealed = Base64.decode(stored, Base64.NO_WRAP)
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, sealed, 0, IV_BYTES))
        return String(cipher.doFinal(sealed, IV_BYTES, sealed.size - IV_BYTES))
    }

    private companion object {
        const val KEYSTORE = "AndroidKeyStore"
        const val ALIAS = "metalarm.tokens"
        const val KEY = "tokens"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val IV_BYTES = 12
    }
}
