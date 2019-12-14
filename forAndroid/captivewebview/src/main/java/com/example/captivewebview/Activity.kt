// Copyright 2019 VMware, Inc.  
// SPDX-License-Identifier: BSD-2-Clause

package com.example.captivewebview

import android.app.Activity
import android.os.Bundle

open class Activity : Activity(), ActivityMixIn {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        onCreateMixIn()
    }

    override fun onResume() {
        super.onResume()
        onResumeMixIn()
    }

    // Following code would implement saving and restoring of the WebView but
    // that seems to be an inferior solution to configuration change handling
    // declaration. See the warnMissingDeclaration() method for details.
    //    override fun onSaveInstanceState(outState: Bundle?) {
    //        val webView =
    //            findViewById<com.example.captivewebview.WebView>(WEB_VIEW_ID)
    //        webView?.saveState(outState)
    //        super.onSaveInstanceState(outState)
    //    }
    //
    //    override fun onRestoreInstanceState(savedInstanceState: Bundle?) {
    //        val webView =
    //            findViewById<com.example.captivewebview.WebView>(WEB_VIEW_ID)
    //        webView?.restoreState(savedInstanceState)
    //        super.onRestoreInstanceState(savedInstanceState)
    //    }

}