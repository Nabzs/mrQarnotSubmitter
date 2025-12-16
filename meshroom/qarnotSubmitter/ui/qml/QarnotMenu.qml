import QtQuick 2.15
import QtQuick.Controls 2.15

Menu {
    title: "Submitter"
    id: menu

    property string email;
    property string status;
    property bool isConnected;
    property string storageInfo;
    property string runningTaskCount;

    signal disconnectSignal(var menu)
    signal connectSignal(var menu)
    signal openSignal(var menu)

    onOpened: {
        openSignal(menu)
    }

    function magicAttach(bar) {
        // 4 en index, car on veut insérer le menu en 4eme position
        bar.insertMenu(4, this);
    }

    // Avec token

    MenuItem {
        text: email
        enabled: false
        visible: isConnected
        height: visible ? implicitHeight : 0
    }
    MenuItem {
        text: runningTaskCount
        enabled: false
        visible: isConnected
        height: visible ? implicitHeight : 0
    }
    MenuItem {
        text: storageInfo
        enabled: false
        visible: isConnected
        height: visible ? implicitHeight : 0
    }
    // MenuItem {
    //     text: "Vider le bucket de sortie"
    //     visible: isConnected
    //     height: visible ? implicitHeight : 0
    // }
    // MenuItem {
    //     text: "Télécharger le bucket de sortie"
    //     visible: isConnected
    //     height: visible ? implicitHeight : 0
    // }
    MenuItem {
        text: "Supprimer le token"
        onTriggered: menu.disconnectSignal(menu)
        visible: isConnected
        height: visible ? implicitHeight : 0
    }

    // Sans token
        
    MenuItem {
        text: "Connexion"
        onTriggered: menu.connectSignal(menu)
        visible: !isConnected
        height: visible ? implicitHeight : 0
    }
}