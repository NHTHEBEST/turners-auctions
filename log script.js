(function(){
    if (window.__turnersLoggerInstalled) return "already-installed";
    window.__turnersLoggerInstalled = true;

    function logger(type, jsondata) {
        var data = JSON.stringify({logtype: type, data: jsondata, id: biddingui.goodNumber});
        var xhr = new XMLHttpRequest();
        var url = "http://localhost:5000";
        xhr.open("POST", url, true);
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.send(data);
    }

    biddingsignalr.turnersconnection.on("liveEvent", function(n) { logger("ws", n); });

    biddingui.serverResponses.receiveGood = function(n) {
        logger("lot", {id: biddingui.goodNumber, data: n});
        biddingui.$goodHeadingName.text(n.Result.goodName);
        biddingui.$bidLoginButton.text(n.Result.loginButtonText);
        biddingui.$tabButtonsContainer.find(".tab-button-vehicle-details span.text").html(n.Result.goodDetailsHeading);
        biddingui.$noticesPanel.html(biddingui.hbTemplates.notices(n.Result.noticesModel));
        biddingui.$tabPanelsContainer.empty();
        biddingui.helpers.assignGoodModel(n);
        biddingui.$tabPanelsContainer.append(biddingui.hbTemplates.commentGood(n.Result.commentGoodModel));
        biddingui.$tabPanelsContainer.children().addClass("active");
        biddingui.$tabPanelsContainer.children(".active").hasClass("tab-content-comments") && (common.comments.init(), common.comments.helpers.commentToggleReadMore());
        common.overlay.addAjaxHandler(biddingui.$noticesPanel.find(".lightbox-ajax-trigger"));
        var t = $("#lot" + biddingui.lotNumber),
            i = biddingui.$lotListContainer.find(".info-widget-widget-content");
        i.scrollTop(i.scrollTop() + t.position().top);
        t.addClass("selected", biddingui.flashSpeed);
        biddingui.set.gallery(n.Result.imagesGoodModel);
        biddingui.animations.goodPanelNextLotLoadingHide();
        biddingui.animations.goodErrorHide();
        biddingui.animations.goodLoadingHide();
        biddingui.animations.goodPanelShow();
    };

    return "ok";
})();
