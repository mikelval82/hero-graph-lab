import TelegramGateway, { format as formatMessage, type Command } from "./gateway";

export class NotificationService {
  constructor(private readonly gateway: TelegramGateway) {}

  async notify(command: Command): Promise<void> {
    const text = formatMessage(command.payload ?? command.name);
    await this.deliver(text);
  }

  private async deliver(text: string): Promise<void> {
    await this.gateway.send(text);
  }
}
