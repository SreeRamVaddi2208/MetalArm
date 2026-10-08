package com.sreeram.metalarm.platform

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network

/** Calls back whenever the network comes back after being down. */
class Connectivity(context: Context) {
    private val manager = context.getSystemService(ConnectivityManager::class.java)
    private var started = false

    fun start(onReconnect: () -> Unit) {
        if (started) return
        started = true
        manager.registerDefaultNetworkCallback(object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) = onReconnect()
        })
    }
}
