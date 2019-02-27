<xsl:stylesheet version="1.0"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:netconf10="urn:ietf:params:xml:ns:netconf:base:1.0"
                xmlns:netconf11="urn:ietf:params:xml:ns:netconf:base:1.1"
                xmlns:ncstate="urn:ietf:params:xml:ns:yang:ietf-netconf-monitoring"
                xmlns:confdstate="http://tail-f.com/yang/confd-monitoring">
  <xsl:output method="text"/>

  <xsl:template match="/">
    <xsl:apply-templates/>
  </xsl:template>

  <xsl:template match="/netconf10:rpc-reply">
    <xsl:apply-templates select="netconf10:data/ncstate:netconf-state/ncstate:schemas/ncstate:schema"/>
    <xsl:apply-templates select="netconf10:data/confdstate:confd-state/confdstate:loaded-data-models/confdstate:data-model"/>
  </xsl:template>

  <xsl:template match="/netconf10:rpc-reply/netconf10:data/ncstate:netconf-state/ncstate:schemas/ncstate:schema[ncstate:format='yang' or ncstate:format='ncm:yang'][ncstate:location='NETCONF']">
    <xsl:text>netconf:</xsl:text><xsl:value-of select="ncstate:identifier"/><xsl:text>
</xsl:text>
  </xsl:template>
  <xsl:template match="/netconf10:rpc-reply/netconf10:data/ncstate:netconf-state/ncstate:schemas/ncstate:schema[ncstate:format='yang' or ncstate:format='ncm:yang'][ncstate:location!='NETCONF']">
    <xsl:text>url:</xsl:text><xsl:value-of select="ncstate:identifier"/><xsl:text>:</xsl:text><xsl:value-of select="ncstate:location"/><xsl:text>
</xsl:text>
  </xsl:template>
  <xsl:template match="/netconf10:rpc-reply/netconf10:data/ncstate:netconf-state/ncstate:schemas/ncstate:schema[ncstate:format='yin']">
    <xsl:text>yin:</xsl:text><xsl:value-of select="ncstate:identifier"/><xsl:text>:</xsl:text><xsl:value-of select="ncstate:location"/><xsl:text>
</xsl:text>
  </xsl:template>
  <xsl:template match="/netconf10:rpc-reply/netconf10:data/ncstate:netconf-state/ncstate:schemas/*"/>

  <xsl:template match="/netconf10:rpc-reply/netconf10:data/confdstate:confd-state/confdstate:loaded-data-models/confdstate:data-model">
    <xsl:text>confd:</xsl:text><xsl:value-of select="confdstate:name"/><xsl:text>
</xsl:text>
  </xsl:template>
  
  <xsl:template match="*">
    <xsl:message terminate="yes">
      WARNING: Unmatched element: <xsl:value-of select="name()"/>
    </xsl:message>
    <xsl:apply-templates/>
  </xsl:template>
  <xsl:template match="text( )|@*"/>
</xsl:stylesheet>
