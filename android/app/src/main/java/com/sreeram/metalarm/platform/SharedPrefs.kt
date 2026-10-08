package com.sreeram.metalarm.platform

import android.content.Context
import com.sreeram.metalarm.state.Prefs

/** App settings (notification and Health Connect toggles) in SharedPreferences. */
class SharedPrefs(context: Context, name: String = "metalarm.settings") : Prefs {
    private val prefs = context.getSharedPreferences(name, Context.MODE_PRIVATE)
    override fun getBoolean(key: String): Boolean? = if (prefs.contains(key)) prefs.getBoolean(key, false) else null
    override fun putBoolean(key: String, value: Boolean) = prefs.edit().putBoolean(key, value).apply()
    override fun getString(key: String): String? = prefs.getString(key, null)
    override fun putString(key: String, value: String) = prefs.edit().putString(key, value).apply()
}
