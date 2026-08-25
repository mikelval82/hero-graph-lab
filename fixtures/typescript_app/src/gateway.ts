export interface MessagePort {
  send(message: string): Promise<void>;
}

export type Command = {
  name: string;
  payload?: string;
};

export enum DeliveryState {
  Pending,
  Sent,
}

export function normalize(message: string): string {
  return message.trim();
}

export default class TelegramGateway implements MessagePort {
  async send(message: string): Promise<void> {
    format(message);
  }
}

export const format = (message: string): string => normalize(message);
