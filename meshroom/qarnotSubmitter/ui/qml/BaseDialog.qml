import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15

Window {
    id: root
    visible: true
    width: 450
    height: 250
    title: "Qarnot Submitter"
    
    x: (Screen.width - width) / 2
    y: (Screen.height - height) / 2
    
    flags: Qt.Dialog | Qt.WindowStaysOnTopHint
    modality: Qt.ApplicationModal 

    // Cette propriété sera remplie par Python
    property var palette
    property string message
    property string buttonText

    // Signal et erreur
    signal cancelSignal(var root)

    onClosing: {
        root.cancelSignal(root)
    }

    // --- FOND DE LA FENÊTRE ---
    // On utilise un Rectangle pour forcer la couleur de fond
    // car Window.color peut parfois être ignoré sous Windows/Mac
    Rectangle {
        anchors.fill: parent
        // On vérifie si 'palette' est défini, sinon on met gris par défaut
        color: root.palette ? root.palette.window : "#323437"
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 10

        Label {
            text: message
            color: root.palette ? root.palette.text : "white"
            font.pixelSize: 14
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            Layout.alignment: Qt.AlignRight
            spacing: 10

            Button {
                id: validateBtn
                text: buttonText
                
                contentItem: Text {
                    text: parent.text
                    color: parent.enabled ? "white" : (root.palette ? root.palette.disabledText : "grey")
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    font.bold: true
                }
                background: Rectangle {
                    // Bleu (Highlight)
                    color: parent.enabled ? 
                           (parent.down && root.palette ? Qt.darker(root.palette.highlight, 1.2) : (root.palette ? root.palette.highlight : "blue")) 
                           : (root.palette ? root.palette.button : "#444")
                    radius: 4
                }

                onClicked: root.cancelSignal(root);
            }
        }
    }
}