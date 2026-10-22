package com.example.smartparking

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

sealed interface Screen {
    object Idle : Screen
    object Finding : Screen
    object Full : Screen
    class Route(val a: Assignment) : Screen
    class Thanks(val number: Int) : Screen
}

class ParkingViewModel : ViewModel() {
    var screen by mutableStateOf<Screen>(Screen.Idle); private set
    var status by mutableStateOf<LotStatus?>(null); private set
    var online by mutableStateOf(true); private set
    var lotMap by mutableStateOf<LotMap?>(null); private set

    init {
        viewModelScope.launch {
            while (true) {
                refresh()
                delay(4000)
            }
        }
    }

    private suspend fun refresh() {
        try {
            val s = Api.status()
            status = s
            online = true
            if (lotMap == null) {
                try { lotMap = Api.map() } catch (e: Exception) { /* retried on next refresh */ }
            }
            if (screen is Screen.Idle && s.free == 0) screen = Screen.Full
            else if (screen is Screen.Full && s.free > 0) screen = Screen.Idle
        } catch (e: Exception) {
            online = false
        }
    }

    fun checkAgain() {
        viewModelScope.launch { refresh() }
    }

    fun find() {
        if (screen !is Screen.Idle) return
        screen = Screen.Finding
        viewModelScope.launch {
            val t0 = System.currentTimeMillis()
            try {
                if (lotMap == null) lotMap = Api.map()
                val a = Api.assign()
                val left = 1300 - (System.currentTimeMillis() - t0)
                if (left > 0) delay(left)
                screen = Screen.Route(a)
            } catch (e: LotFullException) {
                screen = Screen.Full
            } catch (e: Exception) {
                online = false
                screen = Screen.Idle
            }
        }
    }

    fun confirm(a: Assignment) {
        screen = Screen.Thanks(a.number)
        viewModelScope.launch {
            try { Api.confirm(a.id) } catch (e: Exception) { /* hold still expires on its own */ }
        }
    }

    fun reset() {
        screen = Screen.Idle
        viewModelScope.launch { refresh() }
    }
}
