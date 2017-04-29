#-*- coding: utf-8 -*-
# https://github.com/Kodi-vStream/venom-xbmc-addons
#
from resources.lib.handler.inputParameterHandler import cInputParameterHandler
from resources.lib.handler.pluginHandler import cPluginHandler
from resources.lib.config import cConfig
from resources.lib.gui.gui import cGui
from resources.lib.db import cDb
from resources.lib.util import VSlog,isKrypton,VSerror
import xbmc, xbmcgui, xbmcplugin
import xbmcaddon,xbmcvfs
import time

#pour les sous titres
#https://github.com/amet/service.subtitles.demo/blob/master/service.subtitles.demo/service.py
#player API
#http://mirrors.xbmc.org/docs/python-docs/stable/xbmc.html#Player

class cPlayer(xbmc.Player):
    
    def __init__(self, *args):
        
        sPlayerType = self.__getPlayerType()
        xbmc.Player.__init__(self,sPlayerType)
        
        self.Subtitles_file = []
        self.SubtitleActive = False
        
        oInputParameterHandler = cInputParameterHandler()
        #aParams = oInputParameterHandler.getAllParameter()
        #xbmc.log(str(aParams))
        
        self.sHosterIdentifier = oInputParameterHandler.getValue('sHosterIdentifier')
        self.sTitle = oInputParameterHandler.getValue('sTitle')
        #self.sSite = oInputParameterHandler.getValue('site')
        self.sSite = oInputParameterHandler.getValue('siteUrl')
        self.sThumbnail = xbmc.getInfoLabel('ListItem.Art(thumb)')
        
        self.playBackEventReceived = False
        self.playBackStoppedEventReceived = False
        self.forcestop = False        
        
        VSlog("player initialized")
        
    def clearPlayList(self):
        oPlaylist = self.__getPlayList()
        oPlaylist.clear()

    def __getPlayList(self):
        return xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

    def addItemToPlaylist(self, oGuiElement):
        oGui = cGui()
        oListItem =  oGui.createListItem(oGuiElement)
        self.__addItemToPlaylist(oGuiElement, oListItem)
	
    def __addItemToPlaylist(self, oGuiElement, oListItem):    
        oPlaylist = self.__getPlayList()	
        oPlaylist.add(oGuiElement.getMediaUrl(), oListItem )
        
    def AddSubtitles(self,files):
        if isinstance(files, basestring):
            self.Subtitles_file.append(files)
        else:
            self.Subtitles_file = files
        
    def run(self, oGuiElement, sTitle, sUrl):
 
        self.totalTime = 0
        self.currentTime = 0
    
        sPluginHandle = cPluginHandler().getPluginHandle()

        meta = {'label': sTitle, 'title': sTitle}
        item = xbmcgui.ListItem(path=sUrl, iconImage="DefaultVideo.png",  thumbnailImage=self.sThumbnail)
        
        item.setInfo( type="Video", infoLabels= meta )
        
        #lien dash
        if sUrl.endswith('.mpd'):
            if isKrypton() == True:
                cConfig().setSetting("playerPlay",'2')
                self.enable_addon("inputstream.adaptive")
            else:
                VSerror('Nécessite kodi 17 minimum')
                return
        #Sous titres
        if (self.Subtitles_file):
            try:
                item.setSubtitles(self.Subtitles_file)
                VSlog("Load SubTitle :" + str(self.Subtitles_file))               
                self.SubtitleActive = True
            except:
                VSlog("Can't load subtitle :" + str(self.Subtitles_file))
                
        player_conf = cConfig().getSetting("playerPlay")

        #1 er mode de lecture
        if (player_conf == '0'):
            self.play(sUrl,item)
            xbmcplugin.endOfDirectory(sPluginHandle, True, False, False)
            VSlog('Player use Play() method')
        #2 eme mode dash
        elif (player_conf == '2'):
            item.setProperty('inputstreamaddon','inputstream.adaptive')
            item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
            xbmcplugin.setResolvedUrl(sPluginHandle, True, listitem=item)
            VSlog('Player use inputstream addon')
            #remet settings par defaut
            cConfig().setSetting("playerPlay",'1')
        #3 eme mode (defaut)
        else:
            xbmcplugin.setResolvedUrl(sPluginHandle, True, item)
            VSlog('Player use setResolvedUrl() method')
        
        #Attend que le lecteur demarre, avec un max de 20s
        for _ in xrange(20):
            if self.playBackEventReceived:
                break
            xbmc.sleep(1000)
            
        #active/desactive les sous titres suivant l'option choisie dans la config 
        if (self.SubtitleActive):
            if (cConfig().getSetting("srt-view") == 'true'):
                self.showSubtitles(True)
                cGui().showInfo("Sous titre charges", "Sous-Titres", 5)
            else:
                self.showSubtitles(False)
                cGui().showInfo("Sous titre charges, Vous pouvez les activer", "Sous-Titres", 15)
		
       
        while self.isPlaying() and not self.forcestop:
        #while not xbmc.abortRequested:
            try: 
               self.currentTime = self.getTime()
               self.totalTime = self.getTotalTime()
               
               #xbmc.log(str(self.currentTime))
               
            except:
                pass
                #break
            xbmc.sleep(1000)
            
        if not self.playBackStoppedEventReceived:
            self.onPlayBackStopped()
        
        VSlog('Closing player')

    #fonction light servant par exmple pour visualiser les DL ou les chaines de TV
    def startPlayer(self):
        oPlayList = self.__getPlayList()
        self.play(oPlayList)

    def onPlayBackEnded( self ):
        self.onPlayBackStopped()

    #Attention pas de stop, si on lance une seconde video sans fermer la premiere
    def onPlayBackStopped( self ):
        
        VSlog("player stoped")
        
        self.playBackStoppedEventReceived = True
        
        try:
            self.__setWatched()
        except:
            pass
        try:
            self.__setResume()
        except:
            pass
        #xbmc.executebuiltin( 'Container.Refresh' )
        
    def onPlayBackStarted(self):
        
        VSlog("player started")
        
        #Si on recoit une nouvelle fois l'event, c'est que ca buggue, on stope tout
        if self.playBackEventReceived:
            self.forcestop = True
            return
        
        self.playBackEventReceived = True
        
        #inutile sur les dernieres version > Dharma
        if not (cConfig().isDharma()):
            self.__getResume()
            
    def __getResume(self):
        
        meta = {}      
        meta['title'] = self.sTitle
        #meta['hoster'] = self.sHosterIdentifier
        meta['site'] = self.sSite
        
        try:
            data = cDb().get_resume(meta)
            if not data == '':
                time = float(data[0][3]) / 60
                label = '%s %.2f minutes' % ('Reprendre:', time)     
                oDialog = cConfig().createDialogYesNo(label)
                if (oDialog == 1):
                    seekTime = float(data[0][3])
                    self.seekTime(seekTime)
                else: 
                    pass
        except:
            pass        
                
    def __setResume(self):
        
        #inutile sur les dernieres version > Dharma
        if (cConfig().isDharma()):
            return
        
        #Faut pas deconner quand meme
        if self.currentTime < 30:
            return
        
        meta = {}      
        meta['title'] = self.sTitle
        #meta['hoster'] = self.sHosterIdentifier
        meta['site'] = self.sSite
        meta['point'] = str(self.currentTime)
        
        try:
            cDb().insert_resume(meta)
        except:
            pass
            
    def __setWatched(self):
        
        #inutile sur les dernieres version > Dharma
        if (cConfig().isDharma()):
            return
        
        #Faut pas deconner quand meme
        if self.currentTime < 30:
            return
        
        meta = {}      
        meta['title'] = self.sTitle
        meta['site'] = self.sSite
        
        try:
            cDb().insert_watched(meta)
        except:
            pass
        
    def __getPlayerType(self):
        oConfig = cConfig()
        sPlayerType = oConfig.getSetting('playerType')
        
        try:
            if (sPlayerType == '0'):
                VSlog("playertype from config: auto")
                return xbmc.PLAYER_CORE_AUTO

            if (sPlayerType == '1'):
                VSlog("playertype from config: mplayer")
                return xbmc.PLAYER_CORE_MPLAYER

            if (sPlayerType == '2'):
                VSlog("playertype from config: dvdplayer")
                return xbmc.PLAYER_CORE_DVDPLAYER
        except:
            return False
            
    def enable_addon(self,addon):
        import json
        sCheck = {'jsonrpc': '2.0','id': 1,'method': 'Addons.GetAddonDetails','params': {'addonid':'inputstream.adaptive','properties': ['enabled']}}
        response = xbmc.executeJSONRPC(json.dumps(sCheck))
        data = json.loads(response)
        if not 'error' in data.keys():
            if data['result']['addon']['enabled'] == False:
                do_json = '{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"inputstream.adaptive","enabled":true}}'
                query = xbmc.executeJSONRPC(do_json)
                VSlog("Activation d'inputstream.adaptive")
            else:
                VSlog('inputstream.adaptive déjà activé')
                
                
